from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Complaint, ComplaintPhoto
from .serializers import COMPLAINT_PHOTO_MAX_BYTES

URL = '/api/complaints/'
TOKEN = 'k' * 40
JPEG = b'\xff\xd8\xff\xe0' + b'jpeg' * 30
PNG = b'\x89PNG\r\n\x1a\n' + b'png' * 30
HEIC = b'\x00\x00\x00\x18ftypheic' + b'heic' * 30


def photo(content=JPEG, name='photo.jpg', content_type='image/jpeg'):
    return SimpleUploadedFile(name, content, content_type=content_type)


@override_settings(COMPLAINTS_INTAKE_TOKEN=TOKEN, COMPLAINTS_DAILY_BYTES=10 * 1024 * 1024)
class ComplaintsTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user('complaints_test', password='x')
        cls.manager.groups.add(Group.objects.get(name='complaints_managers'))
        cls.hr = User.objects.create_user('hr_test', password='x')
        cls.hr.groups.add(Group.objects.get(name='hr_managers'))
        cls.admin = User.objects.create_superuser('admin_test', password='x')

    def setUp(self):
        cache.clear()

    def payload(self, **changes):
        return {
            'complaint_type': 'waste_issue',
            'full_name': 'Асанова Айгуль',
            'email': 'aigul@example.kg',
            'phone': '+996 700 123 456',
            'subject': 'Не вывезли мусор',
            'description': 'Контейнеры полные\nтретий день',
            'incident_date': '2026-11-09',
            'incident_location': 'ул. Ахунбаева, 100',
            **changes,
        }

    def send(self, token=TOKEN, **changes):
        headers = {'HTTP_X_INTAKE_TOKEN': token} if token is not None else {}
        return self.client.post(URL, self.payload(**changes), format='multipart', **headers)

    def complaint(self, **changes):
        res = self.send(**changes)
        self.assertEqual(res.status_code, 201, res.data)
        return Complaint.objects.get(pk=res.data['id'])


class IntakeFromSiteTests(ComplaintsTestCase):
    def test_site_server_saves_a_complaint(self):
        complaint = self.complaint()

        self.assertEqual(complaint.complaint_type, 'waste_issue')
        self.assertEqual(complaint.full_name, 'Асанова Айгуль')
        self.assertEqual(complaint.description, 'Контейнеры полные\nтретий день')
        self.assertEqual(str(complaint.incident_date), '2026-11-09')
        self.assertEqual(complaint.status, 'new')

    def test_every_type_is_accepted(self):
        for value, _ in Complaint.TYPE_CHOICES:
            self.complaint(complaint_type=value)
        self.assertEqual(Complaint.objects.count(), len(Complaint.TYPE_CHOICES))

    def test_answer_gives_back_only_the_id(self):
        res = self.send()
        self.assertEqual(set(res.data), {'id'})

    def test_date_and_place_are_optional(self):
        payload = self.payload()
        del payload['incident_date'], payload['incident_location']
        res = self.client.post(URL, payload, format='multipart', HTTP_X_INTAKE_TOKEN=TOKEN)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(Complaint.objects.get().incident_date)

    def test_unknown_type_is_rejected(self):
        self.assertEqual(self.send(complaint_type='spam').status_code, 400)
        self.assertFalse(Complaint.objects.exists())

    def test_photos_are_saved_in_order_with_detected_type(self):
        complaint = self.complaint(photos=[
            photo(),
            photo(PNG, 'b.png', 'image/png'),
            photo(HEIC, 'c.jpg', 'image/jpeg'),
        ])
        photos = list(complaint.photos.all())
        self.assertEqual([p.content_type for p in photos], ['image/jpeg', 'image/png', 'image/heic'])
        self.assertEqual(bytes(photos[0].content), JPEG)
        self.assertEqual(photos[1].size, len(PNG))

    def test_not_a_photo_is_rejected(self):
        res = self.send(photos=[photo(b'MZ' + b'\x00' * 100, 'virus.jpg')])
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Complaint.objects.exists())

    def test_more_than_five_photos_is_rejected(self):
        res = self.send(photos=[photo() for _ in range(6)])
        self.assertEqual(res.status_code, 400)

    def test_too_big_photo_is_rejected(self):
        big = JPEG + b'x' * COMPLAINT_PHOTO_MAX_BYTES
        self.assertEqual(self.send(photos=[photo(big)]).status_code, 400)

    @override_settings(COMPLAINTS_DAILY_BYTES=len(JPEG) * 2)
    def test_over_daily_limit_complaint_is_kept_without_photos(self):
        self.complaint(photos=[photo(), photo()])
        complaint = self.complaint(photos=[photo()])

        self.assertEqual(complaint.photos.count(), 0)
        self.assertIn('Фото не сохранены', complaint.manager_note)


class IntakeTokenTests(ComplaintsTestCase):
    def test_without_token_complaint_is_refused(self):
        self.assertIn(self.send(token=None).status_code, (401, 403))
        self.assertFalse(Complaint.objects.exists())

    def test_wrong_token_is_refused(self):
        self.assertIn(self.send(token='x' * 40).status_code, (401, 403))

    @override_settings(COMPLAINTS_INTAKE_TOKEN='')
    def test_nothing_is_accepted_when_token_is_not_configured(self):
        self.assertIn(self.send(token='').status_code, (401, 403))

    @override_settings(COMPLAINTS_INTAKE_TOKEN='short')
    def test_short_token_is_not_trusted(self):
        self.assertIn(self.send(token='short').status_code, (401, 403))

    def test_staff_login_does_not_replace_the_token(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.send(token=None).status_code, 403)


class StaffAccessTests(ComplaintsTestCase):
    def setUp(self):
        super().setUp()
        self.waste = self.complaint(photos=[photo()])
        self.billing = self.complaint(complaint_type='billing_error', full_name='Иванов Иван')

    def test_visitor_sees_nothing(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))
        self.assertIn(self.client.get(f'{URL}{self.waste.pk}/').status_code, (401, 403))

    def test_other_departments_see_nothing(self):
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_manager_sees_complaints_of_every_type(self):
        self.client.force_authenticate(self.manager)
        res = self.client.get(URL)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 2)
        item = next(row for row in res.data['results'] if row['id'] == str(self.waste.pk))
        self.assertEqual(item['type_label'], 'Проблема с вывозом отходов')
        self.assertEqual(item['status_label'], 'Новая')
        self.assertEqual(item['photos'], [{'id': self.waste.photos.get().pk, 'content_type': 'image/jpeg', 'size': len(JPEG)}])

    def test_filters_by_type_and_status(self):
        self.client.force_authenticate(self.manager)
        res = self.client.get(URL, {'complaint_type': 'billing_error'})
        self.assertEqual([row['full_name'] for row in res.data['results']], ['Иванов Иван'])

        Complaint.objects.filter(pk=self.waste.pk).update(status='resolved')
        res = self.client.get(URL, {'status': 'new'})
        self.assertEqual(res.data['count'], 1)

    def test_manager_changes_only_status_and_note(self):
        self.client.force_authenticate(self.manager)
        res = self.client.patch(
            f'{URL}{self.waste.pk}/',
            {'status': 'in_progress', 'manager_note': 'Передано в участок №3', 'full_name': 'Подмена'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)

        self.waste.refresh_from_db()
        self.assertEqual(self.waste.status, 'in_progress')
        self.assertEqual(self.waste.manager_note, 'Передано в участок №3')
        self.assertEqual(self.waste.full_name, 'Асанова Айгуль')

    def test_unknown_status_is_rejected(self):
        self.client.force_authenticate(self.manager)
        res = self.client.patch(f'{URL}{self.waste.pk}/', {'status': 'deleted'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_only_administrator_deletes(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.delete(f'{URL}{self.waste.pk}/').status_code, 403)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f'{URL}{self.waste.pk}/').status_code, 204)
        self.assertFalse(ComplaintPhoto.objects.filter(complaint_id=self.waste.pk).exists())


class PhotoDownloadTests(ComplaintsTestCase):
    def setUp(self):
        super().setUp()
        self.with_photo = self.complaint(photos=[photo()])
        self.photo = self.with_photo.photos.get()
        self.other = self.complaint()
        self.url = f'{URL}{self.with_photo.pk}/photos/{self.photo.pk}/'

    def test_manager_gets_the_file_without_cache(self):
        self.client.force_authenticate(self.manager)
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, JPEG)
        self.assertEqual(res['Content-Type'], 'image/jpeg')
        self.assertEqual(res['Cache-Control'], 'no-store')

    def test_visitor_and_other_departments_get_nothing(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_photo_of_another_complaint_is_not_found(self):
        self.client.force_authenticate(self.manager)
        res = self.client.get(f'{URL}{self.other.pk}/photos/{self.photo.pk}/')
        self.assertEqual(res.status_code, 404)
