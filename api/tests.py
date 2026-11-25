from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Complaint, LocalAct, Procurement, Vacancy, VacancyApplication
from .list_search import phone_digits, search_words


class VacancyApiTests(APITestCase):
    def setUp(self):
        self.driver = Vacancy.objects.create(title_ru='Водитель', salary_from=30000, salary_to=40000)
        self.hidden = Vacancy.objects.create(title_ru='Сварщик', is_active=False)

        self.hr = User.objects.create_user('hr', password='x')
        self.hr.groups.add(Group.objects.get(name='hr_managers'))
        self.content = User.objects.create_user('content', password='x')
        # группы разделов контента создаёт create_users.py, в тестовой базе их нет
        self.content.groups.add(Group.objects.get_or_create(name='content_managers')[0])

    # ---------- сайт ----------
    def test_public_list_shows_only_active(self):
        res = self.client.get('/api/vacancies/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual([v['title_ru'] for v in res.data['results']], ['Водитель'])
        # ?all=1 без прав ничего не открывает
        self.assertEqual(self.client.get('/api/vacancies/?all=1').data['count'], 1)

    def test_inactive_vacancy_not_public(self):
        self.assertEqual(self.client.get(f'/api/vacancies/{self.hidden.id}/').status_code, 404)

    # ---------- права ----------
    def test_anonymous_and_other_staff_cannot_write(self):
        payload = {'title_ru': 'Дворник'}
        self.assertEqual(self.client.post('/api/vacancies/', payload, format='json').status_code, 401)
        self.client.force_authenticate(self.content)
        self.assertEqual(self.client.post('/api/vacancies/', payload, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/vacancies/{self.driver.id}/').status_code, 403)
        # контент-менеджер тоже видит только активные
        self.assertEqual(self.client.get('/api/vacancies/?all=1').data['count'], 1)

    def test_hr_cannot_edit_other_sections(self):
        self.client.force_authenticate(self.hr)
        payload = {'title_ru': 'Новость', 'description_ru': 'Текст', 'date': '2026-10-30'}
        self.assertEqual(self.client.post('/api/news/', payload, format='json').status_code, 403)

    # ---------- отдел кадров ----------
    def test_hr_sees_all_and_filters(self):
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get('/api/vacancies/?all=1').data['count'], 2)
        res = self.client.get('/api/vacancies/?all=1&is_active=0')
        self.assertEqual([v['title_ru'] for v in res.data['results']], ['Сварщик'])
        self.assertEqual(self.client.get(f'/api/vacancies/{self.hidden.id}/').status_code, 200)

    def test_hr_creates_toggles_and_deletes(self):
        self.client.force_authenticate(self.hr)
        res = self.client.post('/api/vacancies/', {
            'title_ru': 'Дворник', 'title_ky': 'Шыпыргыч',
            'requirements_ru': 'Ответственность\nПунктуальность', 'salary_from': 25000,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['is_active'])
        vacancy_id = res.data['id']

        res = self.client.patch(f'/api/vacancies/{vacancy_id}/', {'is_active': False}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(Vacancy.objects.get(id=vacancy_id).is_active)
        # сняли с публикации — с сайта пропала, зарплата осталась
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/vacancies/{vacancy_id}/').status_code, 404)
        self.assertEqual(Vacancy.objects.get(id=vacancy_id).salary_from, 25000)

        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.delete(f'/api/vacancies/{vacancy_id}/').status_code, 204)
        self.assertFalse(Vacancy.objects.filter(id=vacancy_id).exists())

    def test_validation(self):
        self.client.force_authenticate(self.hr)
        res = self.client.post('/api/vacancies/', {'title_ru': '  '}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('title_ru', res.data)

        res = self.client.post('/api/vacancies/', {'title_ru': 'Механик', 'salary_from': 50000, 'salary_to': 40000}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('salary_to', res.data)

        # PATCH одной границы проверяется вместе с сохранённой второй (30 000 – 40 000)
        res = self.client.patch(f'/api/vacancies/{self.driver.id}/', {'salary_to': 20000}, format='json')
        self.assertEqual(res.status_code, 400)


# пароль из локального .env не должен влиять на тесты
@override_settings(ENV={})
class CreateHrUserCommandTests(APITestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command('create_hr_user', *args, stdout=out)
        return out.getvalue()

    @mock.patch.dict('os.environ', {'HR_MANAGER_PASSWORD': 'Kadry-2026-Test'})
    def test_creates_user_only_in_hr_group(self):
        output = self.run_command()
        self.assertIn('HR_MANAGER_PASSWORD', output)
        self.assertNotIn('Kadry-2026-Test', output)

        user = User.objects.get(username='hr_manager')
        self.assertEqual(list(user.groups.values_list('name', flat=True)), ['hr_managers'])
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertTrue(user.check_password('Kadry-2026-Test'))

        res = self.client.post('/api/token/', {'username': 'hr_manager', 'password': 'Kadry-2026-Test'}, format='json')
        self.assertEqual(res.status_code, 200)
        me = self.client.get('/api/me/')
        self.assertEqual(me.data['groups'], ['hr_managers'])

    @mock.patch.dict('os.environ', {'HR_MANAGER_PASSWORD': ''})
    def test_generates_password_and_keeps_it_on_rerun(self):
        output = self.run_command()
        self.assertIn('пароль:', output)
        password = output.split('пароль: ')[1].split()[0]
        self.assertTrue(User.objects.get(username='hr_manager').check_password(password))

        self.assertIn('не менялся', self.run_command())
        self.assertTrue(User.objects.get(username='hr_manager').check_password(password))

        self.run_command('--reset-password')
        self.assertFalse(User.objects.get(username='hr_manager').check_password(password))

    def test_refuses_superuser(self):
        User.objects.create_superuser('boss', password='x')
        with self.assertRaises(Exception):
            self.run_command('--username', 'boss')
        self.assertTrue(User.objects.get(username='boss').is_superuser)

class ListSearchTests(APITestCase):
    """Поиск в списках админки: ?search="""

    def setUp(self):
        self.admin = User.objects.create_superuser('boss', password='x')
        self.client.force_authenticate(self.admin)

    def found(self, url, search, key):
        res = self.client.get(url, {'search': search})
        self.assertEqual(res.status_code, 200)
        return sorted(str(row[key]) for row in res.data['results'])

    def test_procurements_by_number_contract_and_supplier(self):
        for number, contract, supplier in (('11', '314/35', 'ОсОО «Бишкек Строй Сервис»'), ('12', '77-А', 'ОсОО «Ак-Жол»')):
            Procurement.objects.create(number=number, contractNumber=contract, supplier=supplier, date='2026-11-01', amount=1)
        numbers = lambda q: [row['contractNumber'] for row in self.client.get('/api/procurements/', {'search': q}).data['results']]
        self.assertEqual(numbers('строй бишкек'), ['314/35'])
        self.assertEqual(numbers('АК-ЖОЛ'), ['77-А'])
        self.assertEqual(numbers('314/'), ['314/35'])
        self.assertEqual(numbers('нет такого'), [])
        # пустой поиск показывает всё
        self.assertEqual(len(numbers('   ')), 2)

    def test_documents_by_title(self):
        LocalAct.objects.create(title='Правила внутреннего распорядка', file_url='/media/a.pdf', file_name='pravila.pdf', date='2026-11-01')
        LocalAct.objects.create(title='Положение о закупках', file_url='/media/b.pdf', file_name='zakupki.pdf', date='2026-11-01')
        self.assertEqual(self.found('/api/local-acts/', 'распорядка правила', 'title'), ['Правила внутреннего распорядка'])
        self.assertEqual(self.found('/api/local-acts/', 'ZAKUPKI', 'title'), ['Положение о закупках'])

    def test_complaints_by_text_and_phone(self):
        common = {'complaint_type': 'other', 'email': 'a@b.kg', 'description': 'Текст'}
        Complaint.objects.create(full_name='Асанова Айгуль', phone='+996 (700) 12-34-56', subject='Мусор', incident_location='ул. Киевская, 12', **common)
        Complaint.objects.create(full_name='Токтогулов Бакыт', phone='+996555000111', subject='Счёт', **common)
        self.assertEqual(self.found('/api/complaints/', 'айгуль', 'full_name'), ['Асанова Айгуль'])
        self.assertEqual(self.found('/api/complaints/', 'киевская', 'full_name'), ['Асанова Айгуль'])
        for phone in ('0700123456', '+996700123456', '700 123 456', '123456', '(700) 12-34-56'):
            self.assertEqual(self.found('/api/complaints/', phone, 'full_name'), ['Асанова Айгуль'], phone)
        # вместе с фильтром по типу
        self.assertEqual(self.client.get('/api/complaints/', {'search': 'айгуль', 'complaint_type': 'billing_error'}).data['count'], 0)

    def test_applications_and_vacancies(self):
        for name, vacancy in (('Осмонов Нурлан', 'Водитель'), ('Ким Анна', 'Дворник')):
            VacancyApplication.objects.create(full_name=name, vacancy_title=vacancy, phone='+996700000001', resume_content=b'x', resume_name='r.pdf', resume_type='application/pdf', resume_size=1)
        self.assertEqual(self.found('/api/vacancy-applications/', 'водитель', 'full_name'), ['Осмонов Нурлан'])
        Vacancy.objects.create(title_ru='Водитель мусоровоза', title_ky='Айдоочу')
        Vacancy.objects.create(title_ru='Дворник')
        self.assertEqual(self.found('/api/vacancies/', 'айдоочу', 'title_ru'), ['Водитель мусоровоза'])

    def test_odd_input_is_safe(self):
        Procurement.objects.create(number='1', contractNumber='К-1', supplier='Поставщик', date='2026-11-01', amount=1)
        for value in ('\x00', '%', "'; drop table", '\\', '((((', 'а' * 5000, '1 2 3 4 5 6 7 8 9', '[0-9]*', '№'):
            self.assertEqual(self.client.get('/api/procurements/', {'search': value}).status_code, 200, value[:20])
            self.assertEqual(self.client.get('/api/complaints/', {'search': value}).status_code, 200, value[:20])
        # знак % ищется буквально, а не как «любой текст»
        self.assertEqual(self.client.get('/api/procurements/', {'search': '%'}).data['count'], 0)

    def test_private_lists_stay_private(self):
        self.client.force_authenticate(None)
        for url in ('/api/complaints/', '/api/vacancy-applications/', '/api/shop/orders/'):
            self.assertIn(self.client.get(url, {'search': 'а'}).status_code, (401, 403), url)

    def test_phone_digits(self):
        self.assertEqual(phone_digits('+996 (700) 12-34-56'), '700123456')
        self.assertEqual(phone_digits('0700123456'), '700123456')
        self.assertEqual(phone_digits('3456'), '3456')
        self.assertIsNone(phone_digits('345'))
        self.assertIsNone(phone_digits('дом 12'))
        self.assertEqual(search_words('  № 12   мусор '), ['12', 'мусор'])


class MediaCaptionTests(APITestCase):
    """Подписи к фото и видео"""

    PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

    def setUp(self):
        self.client.force_authenticate(User.objects.create_superuser('boss', password='x'))

    def test_photo_caption_is_optional_and_public(self):
        plain = self.client.post('/api/photos/', {'main_image': self.PIXEL, 'date': '2026-11-25'}, format='json')
        self.assertEqual(plain.status_code, 201, plain.data)
        self.assertEqual((plain.data['caption_ru'], plain.data['caption_ky']), ('', ''))
        named = self.client.post('/api/photos/', {'main_image': self.PIXEL, 'date': '2026-11-26', 'caption_ru': 'Субботник', 'caption_ky': 'Ишембилик'}, format='json')
        self.assertEqual(named.status_code, 201, named.data)
        # старая админка подписи не присылает — они не стираются
        res = self.client.put(f"/api/photos/{named.data['id']}/", {'main_image': named.data['main_image'], 'date': '2026-11-27'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['caption_ru'], 'Субботник')
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/photos/').data['results'][0]['caption_ky'], 'Ишембилик')

    def test_too_long_caption_rejected(self):
        res = self.client.post('/api/photos/', {'main_image': self.PIXEL, 'date': '2026-11-25', 'caption_ru': 'а' * 161}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('caption_ru', res.data)
