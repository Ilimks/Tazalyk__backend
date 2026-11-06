"""Проверки защиты API: подбор пароля, удалённые опасные адреса, CORS, лишняя информация."""
import base64
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import serializers
from rest_framework.test import APITestCase
from rest_framework.throttling import AnonRateThrottle

from .media_validation import validate_media, validate_media_list
from .models import News


class SecurityTests(APITestCase):
    def setUp(self):
        # лимиты попыток хранятся в кэше — каждый тест начинает с чистого счётчика
        cache.clear()

    def test_login_bruteforce_is_throttled(self):
        codes = [
            self.client.post('/api/token/', {'username': 'admin', 'password': f'wrong-{i}'}, format='json').status_code
            for i in range(6)
        ]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5], 429)

    def test_spoofed_forwarded_for_does_not_reset_login_limit(self):
        # без прокси (DRF_NUM_PROXIES=0) X-Forwarded-For не влияет на счётчик
        for i in range(5):
            self.client.post('/api/token/', {'username': 'a', 'password': 'b'}, format='json', HTTP_X_FORWARDED_FOR=f'10.0.0.{i}')
        res = self.client.post('/api/token/', {'username': 'a', 'password': 'b'}, format='json', HTTP_X_FORWARDED_FOR='10.9.9.9')
        self.assertEqual(res.status_code, 429)

    def test_removed_endpoints_are_gone(self):
        self.assertEqual(self.client.post('/api/import-data/', {}, format='json').status_code, 404)
        self.assertEqual(self.client.post('/api/admin-login/', {}, format='json').status_code, 404)

    def test_anonymous_cannot_write(self):
        for url in ['/api/news/', '/api/videos/', '/api/photos/', '/api/procurements/', '/api/local-acts/', '/api/legislation/']:
            self.assertEqual(self.client.post(url, {}, format='json').status_code, 401, url)

    @override_settings(DEBUG=False)
    def test_no_browsable_api_html(self):
        res = self.client.get('/api/news/', HTTP_ACCEPT='text/html')
        self.assertNotIn('text/html', res.get('Content-Type', ''))

    @override_settings(CORS_ALLOWED_ORIGINS=['https://mptazalyk.kg'])
    def test_cors_only_for_own_origins(self):
        evil = self.client.options(
            '/api/news/', HTTP_ORIGIN='https://evil.example', HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertNotIn('Access-Control-Allow-Origin', evil)
        own = self.client.options(
            '/api/news/', HTTP_ORIGIN='https://mptazalyk.kg', HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
        )
        self.assertEqual(own.get('Access-Control-Allow-Origin'), 'https://mptazalyk.kg')

    def test_root_does_not_list_endpoints(self):
        body = self.client.get('/').content.decode()
        self.assertNotIn('/admin/', body)

    def test_media_path_traversal_blocked(self):
        res = self.client.get('/media/..%2F..%2Ftazalyk%2Fsettings.py')
        self.assertIn(res.status_code, (400, 404))
        res = self.client.get('/media/../../.env')
        self.assertIn(res.status_code, (400, 404))

    def test_anonymous_requests_are_rate_limited(self):
        with mock.patch.object(AnonRateThrottle, 'rate', '3/min', create=True):
            codes = [self.client.get('/api/news/').status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_public_media_lists_are_capped(self):
        News.objects.bulk_create(
            News(title_ru='t', description_ru='d', date='2026-01-01') for _ in range(25)
        )
        self.assertEqual(len(self.client.get('/api/news/?page_size=100').data['results']), 20)
        staff = User.objects.create_user('editor', password='x')
        self.client.force_authenticate(staff)
        self.assertEqual(len(self.client.get('/api/news/?page_size=100').data['results']), 25)


class MediaUploadApiTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_superuser('boss', password='x'))

    def post_news(self, image):
        return self.client.post(
            '/api/news/',
            {'title_ru': 't', 'description_ru': 'd', 'date': '2026-01-01', 'image': image},
            format='json',
        )

    def test_server_rejects_files_that_skip_admin_checks(self):
        for image in ('javascript:alert(1)', 'data:text/html;base64,PHNjcmlwdD4='):
            self.assertEqual(self.post_news(image).status_code, 400, image)
        self.assertFalse(News.objects.exists())

    def test_normal_photo_is_saved(self):
        photo = 'data:image/jpeg;base64,' + base64.b64encode(b'\xff\xd8\xff\xe0' + b'0' * 40).decode()
        self.assertEqual(self.post_news(photo).status_code, 201)


class LoginMonitoringTests(APITestCase):
    def setUp(self):
        cache.clear()

    def login(self, ip, password='wrong-secret'):
        return self.client.post('/api/token/', {'username': 'admin', 'password': password}, format='json', REMOTE_ADDR=ip)

    @override_settings(TELEGRAM_BOT_TOKEN='token', TELEGRAM_ALERTS_CHAT_ID='1')
    def test_bruteforce_sends_one_alert_without_password(self):
        with mock.patch('shop.telegram.urllib.request.urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value.status = 200
            for _ in range(4):
                self.login('10.1.1.1')
            self.assertEqual(urlopen.call_count, 0)
            # пятая ошибка срабатывает сразу по адресу и по логину, следующие в этот час не шлют
            self.login('10.1.1.1')
            self.assertEqual(urlopen.call_count, 2)
            self.login('10.1.1.2')
            self.assertEqual(urlopen.call_count, 2)
        body = urlopen.call_args_list[0].args[0].data.decode()
        self.assertIn('10.1.1.1', body)
        self.assertNotIn('wrong-secret', body)

    def test_failed_login_is_logged_without_password(self):
        with self.assertLogs('security', level='WARNING') as logs:
            self.login('10.1.1.3')
        self.assertIn('10.1.1.3', logs.output[0])
        self.assertNotIn('wrong-secret', logs.output[0])

    def test_passwords_are_hashed_with_argon2(self):
        self.assertTrue(User.objects.create_user('someone', password='x').password.startswith('argon2'))

    def test_old_password_hash_still_logs_in_and_is_upgraded(self):
        user = User.objects.create(username='old', password=make_password('old-password', hasher='pbkdf2_sha256'))
        res = self.client.post('/api/token/', {'username': 'old', 'password': 'old-password'}, format='json')
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith('argon2'))


class MediaValidationTests(SimpleTestCase):
    @staticmethod
    def data_url(mime, content):
        return f'data:{mime};base64,{base64.b64encode(content).decode()}'

    def test_real_files_and_links_are_accepted(self):
        for value, kind in [
            (self.data_url('image/jpeg', b'\xff\xd8\xff\xe0' + b'0' * 40), 'image'),
            (self.data_url('image/webp', b'RIFF0000WEBP' + b'0' * 40), 'image'),
            (self.data_url('video/mp4', b'\0\0\0\x18ftypisom' + b'0' * 40), 'video'),
            (self.data_url('application/pdf', b'%PDF-1.7' + b'0' * 40), 'document'),
            (self.data_url('text/plain', b'hello'), 'document'),
            ('https://api.mptazalyk.kg/media/a.jpg', 'image'),
            ('/media/a.jpg', 'image'),
            ('', 'image'),
        ]:
            self.assertEqual(validate_media(value, kind), value)

    def test_dangerous_values_are_rejected(self):
        for value, kind in [
            ('javascript:alert(1)', 'document'),
            ('//evil.example/a.jpg', 'image'),
            (self.data_url('text/html', b'<script>alert(1)</script>'), 'document'),
            (self.data_url('image/svg+xml', b'<svg onload=alert(1)>'), 'image'),
            (self.data_url('image/png', b'<script>alert(1)</script>'), 'image'),
            (self.data_url('application/pdf', b'not a pdf file at all'), 'document'),
            ('data:application/pdf;base64,!!!', 'document'),
        ]:
            with self.assertRaises(serializers.ValidationError, msg=value[:40]):
                validate_media(value, kind)

    def test_oversized_file_is_rejected_without_decoding(self):
        value = 'data:image/jpeg;base64,/9j/' + 'A' * (21 * 1024 * 1024 * 4 // 3)
        with self.assertRaises(serializers.ValidationError):
            validate_media(value, 'image')

    def test_gallery_must_be_a_short_list(self):
        with self.assertRaises(serializers.ValidationError):
            validate_media_list('not a list', 'image')
        with self.assertRaises(serializers.ValidationError):
            validate_media_list(['/a.jpg'] * 51, 'image')
