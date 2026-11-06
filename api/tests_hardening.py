"""Защита входа, файлов и открытых форм."""
import base64
import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from .authentication import ACCESS_COOKIE, REFRESH_COOKIE
from .media_files import _parse_range
from .media_validation import is_safe_docx
from .models import LocalAct, News, Photo, Vacancy, VacancyApplication

ADMIN = 'https://admin.example.kg'
MEDIA_DIR = tempfile.mkdtemp()
JPEG = b'\xff\xd8\xff\xe0' + b'photo' * 20
PDF = b'%PDF-1.5\n' + b'document' * 20


def data_url(mime, content):
    return f'data:{mime};base64,{base64.b64encode(content).decode()}'


def docx(*extra, relations=''):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('word/document.xml', '<document/>')
        archive.writestr('word/_rels/document.xml.rels', f'<Relationships>{relations}</Relationships>')
        for name in extra:
            archive.writestr(name, 'x')
    return buffer.getvalue()


@override_settings(ADMIN_ORIGINS=[ADMIN], AUTH_COOKIE_SECURE=True)
class CookieLoginTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('staff', password='correct-horse-battery')

    def setUp(self):
        cache.clear()

    def login(self):
        res = self.client.post('/api/token/', {'username': 'staff', 'password': 'correct-horse-battery'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        return res

    def test_tokens_are_not_visible_to_page_scripts(self):
        res = self.login()

        self.assertEqual(res.data, {'ok': True})
        for name, path in ((ACCESS_COOKIE, '/api/'), (REFRESH_COOKIE, '/api/token/')):
            cookie = res.cookies[name]
            self.assertTrue(cookie['httponly'])
            self.assertTrue(cookie['secure'])
            self.assertEqual(cookie['samesite'], 'Strict')
            self.assertEqual(cookie['path'], path)

    def test_session_works_through_the_cookie(self):
        self.login()
        res = self.client.get('/api/me/', headers={'Origin': ADMIN})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['username'], 'staff')

    def test_reading_from_another_site_is_treated_as_a_visitor(self):
        self.login()
        res = self.client.get('/api/me/', headers={'Origin': 'https://evil.example'})
        self.assertEqual(res.status_code, 401)

    def test_writing_from_another_site_is_refused(self):
        self.user.groups.add(Group.objects.get(name='hr_managers'))
        self.login()
        for origin in ('https://evil.example', 'https://mptazalyk.kg', 'null'):
            with self.subTest(origin):
                res = self.client.post('/api/vacancies/', {'title_ru': 'x'}, format='json', headers={'Origin': origin})
                self.assertEqual(res.status_code, 403)
        self.assertFalse(Vacancy.objects.exists())

    def test_writing_without_origin_is_refused(self):
        self.user.groups.add(Group.objects.get(name='hr_managers'))
        self.login()
        self.assertEqual(self.client.post('/api/vacancies/', {'title_ru': 'x'}, format='json').status_code, 403)

    def test_writing_from_the_admin_panel_works(self):
        self.user.groups.add(Group.objects.get(name='hr_managers'))
        self.login()
        res = self.client.post('/api/vacancies/', {'title_ru': 'Водитель'}, format='json', headers={'Origin': ADMIN})
        self.assertEqual(res.status_code, 201, res.data)

    def test_refresh_reads_the_cookie_and_rotates_it(self):
        old = self.login().cookies[REFRESH_COOKIE].value
        res = self.client.post('/api/token/refresh/', headers={'Origin': ADMIN})

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data, {'ok': True})
        self.assertNotEqual(res.cookies[REFRESH_COOKIE].value, old)

    def test_old_refresh_token_stops_working_after_rotation(self):
        old = self.login().cookies[REFRESH_COOKIE].value
        self.client.post('/api/token/refresh/', headers={'Origin': ADMIN})

        thief = APIClient()
        thief.cookies[REFRESH_COOKIE] = old
        self.assertEqual(thief.post('/api/token/refresh/', headers={'Origin': ADMIN}).status_code, 401)

    def test_refresh_from_another_site_is_refused(self):
        self.login()
        self.assertEqual(self.client.post('/api/token/refresh/', headers={'Origin': 'https://evil.example'}).status_code, 403)

    def test_refresh_without_cookie_is_refused(self):
        self.assertEqual(self.client.post('/api/token/refresh/', headers={'Origin': ADMIN}).status_code, 401)

    def test_logout_revokes_the_token_on_the_server(self):
        stolen = self.login().cookies[REFRESH_COOKIE].value
        res = self.client.post('/api/token/logout/', headers={'Origin': ADMIN})

        self.assertEqual(res.status_code, 204)
        self.assertEqual(res.cookies[ACCESS_COOKIE].value, '')
        self.assertEqual(res.cookies[REFRESH_COOKIE].value, '')

        thief = APIClient()
        thief.cookies[REFRESH_COOKIE] = stolen
        self.assertEqual(thief.post('/api/token/refresh/', headers={'Origin': ADMIN}).status_code, 401)

    def test_logout_from_another_site_is_refused(self):
        self.login()
        self.assertEqual(self.client.post('/api/token/logout/', headers={'Origin': 'https://evil.example'}).status_code, 403)

    def test_changing_the_password_ends_all_sessions(self):
        access = self.login().cookies[ACCESS_COOKIE].value
        self.user.set_password('a-new-long-password-2026')
        self.user.save()

        stolen = APIClient()
        stolen.cookies[ACCESS_COOKIE] = access
        self.assertEqual(stolen.get('/api/me/', headers={'Origin': ADMIN}).status_code, 401)


class OpenFormsTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_deeply_nested_json_is_a_bad_request(self):
        body = '[' * 100000 + ']' * 100000
        res = self.client.post('/api/shop/orders/', body, content_type='application/json')
        self.assertEqual(res.status_code, 400)


class ResumeCheckTests(SimpleTestCase):
    def test_ordinary_document_passes(self):
        link = (
            '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"'
            ' Target="https://example.kg" TargetMode="External"/>'
        )
        self.assertTrue(is_safe_docx(docx(relations=link)))

    def test_macro_document_is_rejected(self):
        self.assertFalse(is_safe_docx(docx('word/vbaProject.bin')))

    def test_embedded_program_is_rejected(self):
        self.assertFalse(is_safe_docx(docx('word/embeddings/oleObject1.bin')))

    def test_remote_template_is_rejected(self):
        template = (
            '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate"'
            ' Target="https://evil.example/t.dotm" TargetMode="External"/>'
        )
        self.assertFalse(is_safe_docx(docx(relations=template)))

    def test_any_other_archive_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('program.exe', 'x')
        self.assertFalse(is_safe_docx(buffer.getvalue()))

    def test_archive_bomb_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('word/document.xml', b'0' * (60 * 1024 * 1024))
        self.assertLess(len(buffer.getvalue()), 1024 * 1024)
        self.assertFalse(is_safe_docx(buffer.getvalue()))

    def test_broken_archive_is_rejected(self):
        self.assertFalse(is_safe_docx(b'PK\x03\x04' + b'x' * 64))


class RangeEdgeTests(SimpleTestCase):
    def test_empty_suffix_is_outside_the_file(self):
        with self.assertRaises(ValueError):
            _parse_range('bytes=-0', 100)

    def test_suffix_longer_than_the_file_gives_the_whole_file(self):
        self.assertEqual(_parse_range('bytes=-500', 100), (0, 99))


@override_settings(MEDIA_ROOT=MEDIA_DIR, PUBLIC_MEDIA_BASE_URL='')
class StoredMediaTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_authenticate(User.objects.create_superuser('media_admin', password='x'))

    def tearDown(self):
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)

    def files(self, folder):
        return sorted(path.name for path in (Path(MEDIA_DIR) / folder).glob('*'))

    def test_news_image_is_a_file(self):
        res = self.client.post('/api/news/', {
            'title_ru': 'Новость', 'description_ru': 'Текст', 'date': '2026-11-01',
            'image': data_url('image/jpeg', JPEG),
        }, format='json')

        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['image'].startswith('http://testserver/media/news/'))
        self.assertTrue(News.objects.get().image.startswith('/media/news/'))
        self.assertEqual(len(self.files('news')), 1)

    def test_photo_and_gallery_are_files(self):
        image = data_url('image/jpeg', JPEG)
        res = self.client.post('/api/photos/', {
            'main_image': image, 'gallery_images': [image, image], 'date': '2026-11-01',
        }, format='json')

        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(len(self.files('photos')), 3)
        self.assertTrue(Photo.objects.get().gallery_images[0].startswith('/media/photos/'))

    def test_document_is_a_file_and_list_stays_small(self):
        res = self.client.post('/api/local-acts/', {
            'title': 'Акт', 'file_url': data_url('application/pdf', PDF * 1000),
            'file_name': 'Акт.pdf', 'file_size': len(PDF) * 1000, 'date': '2026-11-01',
        }, format='json')

        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(LocalAct.objects.get().file_url.startswith('/media/documents/'))
        self.assertLess(len(self.client.get('/api/local-acts/').content), 1000)

    def test_saving_a_news_item_with_its_link_keeps_the_file(self):
        created = self.client.post('/api/news/', {
            'title_ru': 'Новость', 'description_ru': 'Текст', 'date': '2026-11-01',
            'image': data_url('image/jpeg', JPEG),
        }, format='json').data
        files = self.files('news')

        res = self.client.put(f"/api/news/{created['id']}/", {
            'title_ru': 'Новость 2', 'description_ru': 'Текст', 'date': '2026-11-01', 'image': created['image'],
        }, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.files('news'), files)

    def test_deleting_a_record_deletes_its_files(self):
        image = data_url('image/jpeg', JPEG)
        created = self.client.post('/api/photos/', {'main_image': image, 'gallery_images': [image], 'date': '2026-11-01'}, format='json').data

        self.assertEqual(self.client.delete(f"/api/photos/{created['id']}/").status_code, 204)
        self.assertEqual(self.files('photos'), [])

    def test_uploaded_file_keeps_only_a_safe_extension(self):
        self.client.post('/api/news/', {
            'title_ru': 'Новость', 'description_ru': 'Текст', 'date': '2026-11-01',
            'image': data_url('image/jpeg', JPEG),
        }, format='json')
        self.assertTrue(self.files('news')[0].endswith('.jpg'))

    def test_html_and_svg_never_become_files(self):
        for mime, content in (('text/html', b'<script>1</script>'), ('image/svg+xml', b'<svg onload="1"/>')):
            with self.subTest(mime):
                res = self.client.post('/api/news/', {
                    'title_ru': 'Новость', 'description_ru': 'Текст', 'date': '2026-11-01',
                    'image': data_url(mime, content),
                }, format='json')
                self.assertEqual(res.status_code, 400)
        self.assertEqual(self.files('news'), [])


@override_settings(APPLICATIONS_DAILY_BYTES=1000)
class ApplicationLimitsTests(APITestCase):
    URL = '/api/vacancy-applications/'

    @classmethod
    def setUpTestData(cls):
        cls.vacancy = Vacancy.objects.create(title_ru='Водитель')

    def setUp(self):
        cache.clear()

    def apply(self, phone, content=b'%PDF-1.5' + b'x' * 600):
        return self.client.post(self.URL, {
            'vacancy': str(self.vacancy.pk), 'full_name': 'Асанов Бакыт', 'phone': phone, 'consent': 'true',
            'resume': io.BytesIO(content),
        }, format='multipart')

    def test_same_person_cannot_apply_twice_a_day(self):
        self.assertEqual(self.apply('+996 700 123 456').status_code, 201)

        for phone in ('+996 700 123 456', '0700 123 456', '996700123456'):
            with self.subTest(phone):
                res = self.apply(phone)
                self.assertEqual(res.status_code, 400)
                self.assertIn('duplicate', res.data)
        self.assertEqual(VacancyApplication.objects.count(), 1)

    def test_daily_total_stops_mass_uploads(self):
        self.assertEqual(self.apply('+996 700 123 456').status_code, 201)
        self.assertEqual(self.apply('+996 700 123 457').status_code, 201)

        self.assertEqual(self.apply('+996 700 123 458').status_code, 429)
        self.assertEqual(VacancyApplication.objects.count(), 2)
