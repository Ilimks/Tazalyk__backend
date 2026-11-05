from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Vacancy


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
        me = self.client.get('/api/me/', HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
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
