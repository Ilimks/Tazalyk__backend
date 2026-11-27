import os
import shutil
import tempfile
import time
from io import StringIO
from urllib.parse import urlsplit

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Video

MEDIA_DIR = tempfile.mkdtemp()
MP4 = b'\x00\x00\x00\x18ftypmp42' + bytes(range(256)) * 4
JPEG = b'\xff\xd8\xff\xe0' + b'preview' * 20
PDF = b'%PDF-1.7\n' + b'0' * 64


def upload(name, content, mime):
    return SimpleUploadedFile(name, content, content_type=mime)


@override_settings(MEDIA_ROOT=MEDIA_DIR, PUBLIC_MEDIA_BASE_URL='')
class UploadTests(APITestCase):
    URL = '/api/uploads/'

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)

    def setUp(self):
        self.editor = User.objects.create_user('content', password='x')
        self.editor.groups.add(Group.objects.get_or_create(name='content_managers')[0])
        self.lawyer = User.objects.create_user('lawyer', password='x')
        self.lawyer.groups.add(Group.objects.get_or_create(name='legal_managers')[0])

    def send(self, user, section, kind, file):
        self.client.force_authenticate(user)
        return self.client.post(self.URL, {'section': section, 'kind': kind, 'file': file}, format='multipart')

    def test_anonymous_cannot_upload(self):
        response = self.client.post(self.URL, {'section': 'videos', 'kind': 'video', 'file': upload('a.mp4', MP4, 'video/mp4')}, format='multipart')
        self.assertIn(response.status_code, (401, 403))

    def test_video_is_stored_and_returned_as_link(self):
        response = self.send(self.editor, 'videos', 'video', upload('a.mp4', MP4, 'video/mp4'))
        self.assertEqual(response.status_code, 201, response.data)
        path = urlsplit(response.data['url']).path
        self.assertRegex(path, r'^/media/videos/[0-9a-f]{32}\.mp4$')
        self.assertTrue(os.path.exists(os.path.join(MEDIA_DIR, path.removeprefix('/media/'))))

    def test_link_is_accepted_when_saving_video(self):
        video = self.send(self.editor, 'videos', 'video', upload('a.mp4', MP4, 'video/mp4')).data['url']
        thumb = self.send(self.editor, 'videos', 'image', upload('t.jpg', JPEG, 'image/jpeg')).data['url']
        response = self.client.post('/api/videos/', {
            'main_video_url': video, 'thumbnail': thumb, 'gallery_videos': [], 'caption_ru': 'Субботник', 'date': '2026-11-27',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        stored = Video.objects.get()
        self.assertEqual(stored.main_video_url, urlsplit(video).path)
        self.assertEqual(stored.thumbnail, urlsplit(thumb).path)

    def test_wrong_type_size_and_content_are_refused(self):
        self.assertEqual(self.send(self.editor, 'photos', 'image', upload('a.exe', b'MZ' * 10, 'application/x-msdownload')).status_code, 400)
        self.assertEqual(self.send(self.editor, 'photos', 'image', upload('a.jpg', b'not an image', 'image/jpeg')).status_code, 400)
        self.assertEqual(self.send(self.editor, 'photos', 'image', upload('a.jpg', b'', 'image/jpeg')).status_code, 400)
        with self.settings():
            from . import media_validation
            types, _ = media_validation.KINDS['image']
            media_validation.KINDS['image'] = (types, 10)
            try:
                response = self.send(self.editor, 'photos', 'image', upload('a.jpg', JPEG, 'image/jpeg'))
            finally:
                media_validation.KINDS['image'] = (types, 20 * media_validation.MB)
        self.assertEqual(response.status_code, 400)
        self.assertIn('МБ', str(response.data['file']))

    def test_section_and_kind_must_match(self):
        self.assertEqual(self.send(self.editor, 'photos', 'video', upload('a.mp4', MP4, 'video/mp4')).status_code, 400)

    def test_rights_follow_the_section(self):
        self.assertEqual(self.send(self.editor, 'legislation', 'document', upload('a.pdf', PDF, 'application/pdf')).status_code, 403)
        response = self.send(self.lawyer, 'legislation', 'document', upload('a.pdf', PDF, 'application/pdf'))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(urlsplit(response.data['url']).path, r'^/media/documents/')

    def test_limits_are_published_for_the_admin(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['video']['maxBytes'], 100 * 1024 * 1024)
        self.assertIn('application/pdf', response.data['document']['types'])

    def test_orphan_files_are_cleaned_after_a_day(self):
        kept = self.send(self.editor, 'photos', 'image', upload('a.jpg', JPEG, 'image/jpeg')).data['url']
        orphan = self.send(self.editor, 'photos', 'image', upload('b.jpg', JPEG, 'image/jpeg')).data['url']
        fresh = self.send(self.editor, 'photos', 'image', upload('c.jpg', JPEG, 'image/jpeg')).data['url']
        self.client.post('/api/photos/', {'main_image': kept, 'gallery_images': [], 'caption_ru': 'Сквер', 'date': '2026-11-27'}, format='json')
        old = time.time() - 2 * 24 * 3600
        local = lambda url: os.path.join(MEDIA_DIR, urlsplit(url).path.removeprefix('/media/'))
        for url in (kept, orphan):
            os.utime(local(url), (old, old))
        out = StringIO()
        call_command('clean_orphan_media', stdout=out)
        exists = lambda url: os.path.exists(local(url))
        self.assertTrue(exists(kept))
        self.assertFalse(exists(orphan))
        self.assertTrue(exists(fresh))
        self.assertIn('1', out.getvalue())
