"""Видео и превью как файлы: загрузка, правка, удаление, перенос старых записей, отдача по частям."""
import base64
import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from imageio_ffmpeg import get_ffmpeg_exe
from rest_framework.test import APITestCase

from .media_files import _needs_faststart, make_faststart
from .models import Video

MEDIA_DIR = tempfile.mkdtemp()
# настоящее начало MP4 и JPEG: сервер сверяет содержимое с типом
MP4 = b'\x00\x00\x00\x18ftypmp42' + bytes(range(256)) * 4
JPEG = b'\xff\xd8\xff\xe0' + b'preview' * 20


def data_url(mime, content):
    return f'data:{mime};base64,{base64.b64encode(content).decode()}'


@override_settings(MEDIA_ROOT=MEDIA_DIR, PUBLIC_MEDIA_BASE_URL='')
class VideoFilesTests(APITestCase):
    URL = '/api/videos/'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_authenticate(User.objects.create_superuser('media_admin', password='x'))
        self.video_url = data_url('video/mp4', MP4)
        self.thumbnail = data_url('image/jpeg', JPEG)

    def stored_files(self):
        return sorted(path.name for path in Path(MEDIA_DIR).glob('videos/*'))

    def upload(self, **extra):
        payload = {
            'main_video_url': self.video_url,
            'thumbnail': self.thumbnail,
            'gallery_videos': [self.video_url],
            'date': '2026-11-01',
            **extra,
        }
        res = self.client.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def tearDown(self):
        shutil.rmtree(Path(MEDIA_DIR) / 'videos', ignore_errors=True)

    def test_upload_keeps_only_a_path_in_the_database(self):
        created = self.upload()
        video = Video.objects.get(pk=created['id'])

        self.assertRegex(video.main_video_url, r'^/media/videos/[0-9a-f]{32}\.mp4$')
        self.assertRegex(video.thumbnail, r'^/media/videos/[0-9a-f]{32}\.jpg$')
        self.assertRegex(video.gallery_videos[0], r'^/media/videos/[0-9a-f]{32}\.mp4$')
        self.assertEqual(len(self.stored_files()), 3)

    def test_api_gives_full_links_and_no_file_content(self):
        self.upload()
        res = self.client.get(self.URL)
        item = res.data['results'][0]

        self.assertTrue(item['main_video_url'].startswith('http://testserver/media/videos/'))
        self.assertTrue(item['thumbnail'].startswith('http://testserver/media/videos/'))
        self.assertLess(len(res.content), 1000)

    @override_settings(PUBLIC_MEDIA_BASE_URL='https://api.example.kg')
    def test_public_address_comes_from_settings_behind_a_proxy(self):
        created = self.upload()
        self.assertTrue(created['main_video_url'].startswith('https://api.example.kg/media/videos/'))

    def test_saving_with_links_from_the_api_keeps_the_files(self):
        created = self.upload()
        before = self.stored_files()

        res = self.client.put(f"{self.URL}{created['id']}/", {
            'main_video_url': created['main_video_url'],
            'thumbnail': created['thumbnail'],
            'gallery_videos': created['gallery_videos'],
            'date': '2026-11-02',
        }, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.stored_files(), before)
        # домен в базу не попадает: иначе после смены адреса API ссылки бы умерли
        self.assertTrue(Video.objects.get(pk=created['id']).main_video_url.startswith('/media/'))

    def test_replaced_file_is_deleted(self):
        created = self.upload(gallery_videos=[])
        res = self.client.put(f"{self.URL}{created['id']}/", {
            'main_video_url': data_url('video/mp4', MP4 + b'new'),
            'thumbnail': created['thumbnail'],
            'gallery_videos': [],
            'date': '2026-11-02',
        }, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(self.stored_files()), 2)
        self.assertNotIn(created['main_video_url'].rsplit('/', 1)[-1], self.stored_files())

    def test_deleted_video_removes_its_files(self):
        created = self.upload()
        self.assertEqual(self.client.delete(f"{self.URL}{created['id']}/").status_code, 204)
        self.assertEqual(self.stored_files(), [])

    def test_damaged_file_is_rejected_without_leaving_a_record(self):
        broken = 'data:video/mp4;base64,' + base64.b64encode(MP4[:12]).decode() + '@@@'
        res = self.client.post(self.URL, {'main_video_url': broken, 'date': '2026-11-01'}, format='json')

        self.assertEqual(res.status_code, 400)
        self.assertFalse(Video.objects.exists())

    def test_link_cannot_point_outside_the_videos_folder(self):
        created = self.upload(gallery_videos=[])
        foreign = '/media/videos/../shop/products/photo.jpg'
        res = self.client.put(f"{self.URL}{created['id']}/", {
            'main_video_url': foreign,
            'date': '2026-11-02',
            'gallery_videos': [],
        }, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Video.objects.get(pk=created['id']).main_video_url, foreign)
        self.client.delete(f"{self.URL}{created['id']}/")
        self.assertEqual(self.client.get(foreign).status_code, 404)

    def test_old_records_work_until_they_are_moved(self):
        video = Video.objects.create(
            main_video_url=self.video_url, thumbnail=self.thumbnail,
            gallery_videos=[self.video_url], date='2026-01-01',
        )
        self.assertEqual(self.client.get(f'{self.URL}{video.pk}/').data['main_video_url'], self.video_url)

        out = StringIO()
        call_command('move_media_to_files', stdout=out)
        video.refresh_from_db()

        self.assertIn('Перенесено записей: 1', out.getvalue())
        self.assertTrue(video.main_video_url.startswith('/media/videos/'))
        self.assertTrue(video.thumbnail.startswith('/media/videos/'))
        self.assertEqual(len(self.stored_files()), 3)

        content = b''.join(self.client.get(video.main_video_url).streaming_content)
        self.assertEqual(content, MP4)

    def test_moving_twice_changes_nothing(self):
        Video.objects.create(main_video_url=self.video_url, date='2026-01-01')
        call_command('move_media_to_files', stdout=StringIO())
        files = self.stored_files()

        out = StringIO()
        call_command('move_media_to_files', stdout=out)

        self.assertIn('Перенесено записей: 0', out.getvalue())
        self.assertEqual(self.stored_files(), files)

    def test_record_with_damaged_data_is_reported_and_left_alone(self):
        broken = 'data:video/mp4;base64,@@@'
        video = Video.objects.create(main_video_url=broken, date='2026-01-01')
        out, err = StringIO(), StringIO()

        call_command('move_media_to_files', stdout=out, stderr=err)
        video.refresh_from_db()

        self.assertEqual(video.main_video_url, broken)
        self.assertIn('с ошибкой: 1', out.getvalue())
        self.assertIn(str(video.pk), err.getvalue())


@override_settings(MEDIA_ROOT=MEDIA_DIR, PUBLIC_MEDIA_BASE_URL='')
class MediaRangeTests(APITestCase):
    PATH = '/media/videos/range.mp4'
    CONTENT = bytes(range(256)) * 4

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        folder = Path(MEDIA_DIR) / 'videos'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'range.mp4').write_bytes(cls.CONTENT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)
        super().tearDownClass()

    def fetch(self, range_header=None):
        headers = {'Range': range_header} if range_header else {}
        return self.client.get(self.PATH, headers=headers)

    def body(self, res):
        return b''.join(res.streaming_content)

    def test_whole_file_says_ranges_are_supported(self):
        res = self.fetch()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Accept-Ranges'], 'bytes')
        self.assertEqual(res['Content-Type'], 'video/mp4')
        self.assertIn('immutable', res['Cache-Control'])
        self.assertEqual(self.body(res), self.CONTENT)

    def test_part_of_the_file(self):
        res = self.fetch('bytes=100-199')
        self.assertEqual(res.status_code, 206)
        self.assertEqual(res['Content-Range'], f'bytes 100-199/{len(self.CONTENT)}')
        self.assertEqual(res['Content-Length'], '100')
        self.assertEqual(res['Content-Type'], 'video/mp4')
        self.assertEqual(self.body(res), self.CONTENT[100:200])

    def test_from_a_position_to_the_end(self):
        res = self.fetch('bytes=1000-')
        self.assertEqual(res.status_code, 206)
        self.assertEqual(self.body(res), self.CONTENT[1000:])

    def test_last_bytes(self):
        res = self.fetch('bytes=-24')
        self.assertEqual(res.status_code, 206)
        self.assertEqual(self.body(res), self.CONTENT[-24:])

    def test_end_past_the_file_is_cut_to_its_size(self):
        res = self.fetch('bytes=1020-999999')
        self.assertEqual(res.status_code, 206)
        self.assertEqual(self.body(res), self.CONTENT[1020:])

    def test_range_outside_the_file(self):
        res = self.fetch(f'bytes={len(self.CONTENT)}-')
        self.assertEqual(res.status_code, 416)
        self.assertEqual(res['Content-Range'], f'bytes */{len(self.CONTENT)}')

    def test_unknown_range_gives_the_whole_file(self):
        res = self.fetch('items=0-5')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.body(res), self.CONTENT)

    def test_missing_file_and_path_traversal(self):
        self.assertEqual(self.client.get('/media/videos/none.mp4').status_code, 404)
        self.assertEqual(self.client.get('/media/../manage.py').status_code, 400)
        self.assertEqual(self.client.get('/media/videos/').status_code, 404)


def atom(kind, payload=b''):
    return (8 + len(payload)).to_bytes(4, 'big') + kind + payload


class FaststartDetectionTests(SimpleTestCase):
    def needs_faststart(self, content):
        with tempfile.NamedTemporaryFile(suffix='.mp4') as file:
            file.write(content)
            file.flush()
            return _needs_faststart(file.name)

    def test_index_before_data_is_ready_for_streaming(self):
        self.assertFalse(self.needs_faststart(atom(b'ftyp', b'x' * 8) + atom(b'moov', b'x' * 64) + atom(b'mdat', b'x' * 512)))

    def test_index_after_data_needs_preparing(self):
        self.assertTrue(self.needs_faststart(atom(b'ftyp', b'x' * 8) + atom(b'mdat', b'x' * 512) + atom(b'moov', b'x' * 64)))

    def test_fragmented_file_needs_preparing(self):
        self.assertTrue(self.needs_faststart(atom(b'ftyp') + atom(b'moov') + atom(b'moof') + atom(b'mdat', b'x' * 512)))

    def test_damaged_files_do_not_hang_or_crash(self):
        self.assertFalse(self.needs_faststart(b''))
        self.assertFalse(self.needs_faststart(bytes([0, 0])))
        self.assertFalse(self.needs_faststart(bytes([0, 0, 0, 0]) + b'ftyp'))
        self.assertFalse(self.needs_faststart(bytes([0, 0, 0, 4]) + b'ftypxxxx'))
        self.assertFalse(self.needs_faststart(bytes([0, 0, 0, 1]) + b'ftyp'))


@override_settings(MEDIA_ROOT=MEDIA_DIR, PUBLIC_MEDIA_BASE_URL='')
class FaststartTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fragmented.mp4'
            subprocess.run([
                get_ffmpeg_exe(), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=64x64:rate=5',
                '-c:v', 'mpeg4', '-movflags', 'frag_keyframe+empty_moov', str(path),
            ], check=True)
            cls.fragmented = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_authenticate(User.objects.create_superuser('media_admin', password='x'))

    def stored_path(self, video):
        return Path(MEDIA_DIR) / video.main_video_url.removeprefix('/media/')

    def test_uploaded_fragmented_video_is_prepared(self):
        res = self.client.post('/api/videos/', {
            'main_video_url': data_url('video/mp4', self.fragmented),
            'date': '2026-11-01',
        }, format='json')

        self.assertEqual(res.status_code, 201, res.data)
        path = self.stored_path(Video.objects.get(pk=res.data['id']))
        self.assertFalse(_needs_faststart(path))
        self.assertEqual(path.read_bytes()[4:8], b'ftyp')

    def test_command_prepares_files_moved_earlier(self):
        folder = Path(MEDIA_DIR) / 'videos'
        folder.mkdir(parents=True, exist_ok=True)
        name = 'a' * 32 + '.mp4'
        (folder / name).write_bytes(self.fragmented)
        Video.objects.create(main_video_url=f'/media/videos/{name}', date='2026-01-01')

        out = StringIO()
        call_command('move_media_to_files', stdout=out)
        self.assertIn('подготовлено видео: 1', out.getvalue())
        self.assertFalse(_needs_faststart(folder / name))

        out = StringIO()
        call_command('move_media_to_files', stdout=out)
        self.assertIn('подготовлено видео: 0', out.getvalue())

    def test_file_stays_when_the_tool_fails(self):
        folder = Path(MEDIA_DIR) / 'videos'
        folder.mkdir(parents=True, exist_ok=True)
        name = 'b' * 32 + '.mp4'
        (folder / name).write_bytes(self.fragmented)

        error = subprocess.CalledProcessError(1, 'ffmpeg')
        with mock.patch('api.media_files.subprocess.run', side_effect=error):
            self.assertFalse(make_faststart(f'videos/{name}'))

        self.assertEqual((folder / name).read_bytes(), self.fragmented)
        self.assertEqual([path.name for path in folder.glob(f'{name}*')], [name])
