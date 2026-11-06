"""Отклики на вакансии: отправка с сайта, закрытый доступ к личным данным, файл резюме."""
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from .excel import FIRST_DATA_ROW, HEADER_ROW, XLSX_CONTENT_TYPE
from .media_validation import RESUME_MAX_BYTES
from .models import Vacancy, VacancyApplication
from .tests_hardening import docx

URL = '/api/vacancy-applications/'
PDF = b'%PDF-1.5\n' + b'resume' * 50


def resume_file(content=PDF, name='cv.pdf', content_type='application/pdf'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class ApplicationsTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vacancy = Vacancy.objects.create(title_ru='Водитель', title_ky='Айдоочу')
        cls.closed_vacancy = Vacancy.objects.create(title_ru='Закрытая', is_active=False)
        cls.hr = User.objects.create_user('hr_test', password='x')
        cls.hr.groups.add(Group.objects.get(name='hr_managers'))
        cls.content_manager = User.objects.create_user('content_test', password='x')
        cls.content_manager.groups.add(Group.objects.get_or_create(name='content_managers')[0])

    def setUp(self):
        # лимит частоты общий на все тесты
        cache.clear()

    def payload(self, **changes):
        return {
            'vacancy': str(self.vacancy.pk),
            'full_name': 'Асанов Бакыт',
            'phone': '+996 700 123 456',
            'email': 'bakyt@example.kg',
            'comment': 'Стаж 5 лет',
            'resume': resume_file(),
            'consent': 'true',
            **changes,
        }

    def apply(self, **changes):
        return self.client.post(URL, self.payload(**changes), format='multipart')

    def application(self):
        res = self.apply()
        self.assertEqual(res.status_code, 201, res.data)
        return VacancyApplication.objects.get()


class ApplyFromSiteTests(ApplicationsTestCase):
    def test_visitor_sends_a_resume(self):
        application = self.application()

        self.assertEqual(application.full_name, 'Асанов Бакыт')
        self.assertEqual(application.vacancy_title, 'Водитель')
        self.assertEqual(application.status, 'new')
        self.assertEqual(bytes(application.resume_content), PDF)
        self.assertEqual(application.resume_size, len(PDF))
        self.assertEqual(application.resume_name, 'Резюме Асанов Бакыт.pdf')

    def test_answer_gives_nothing_back(self):
        self.assertEqual(self.apply().data, {'ok': True})

    def test_email_and_comment_are_optional(self):
        payload = self.payload()
        del payload['email'], payload['comment']
        self.assertEqual(self.client.post(URL, payload, format='multipart').status_code, 201)

    def test_word_and_photo_are_accepted(self):
        samples = {
            'cv.docx': docx(),
            'cv.jpg': b'\xff\xd8\xff\xe0' + b'x' * 64,
            'cv.png': b'\x89PNG\r\n\x1a\n' + b'x' * 64,
        }
        for index, (name, content) in enumerate(samples.items()):
            with self.subTest(name):
                res = self.apply(resume=resume_file(content, name), phone=f'+996 700 000 00{index}')
                self.assertEqual(res.status_code, 201, res.data)
        extensions = {item.resume_name.rsplit('.', 1)[1] for item in VacancyApplication.objects.all()}
        self.assertEqual(extensions, {'docx', 'jpg', 'png'})

    def test_old_word_format_is_rejected_because_of_macros(self):
        res = self.apply(resume=resume_file(b'\xd0\xcf\x11\xe0' + b'x' * 64, 'cv.doc'))
        self.assertEqual(res.status_code, 400)
        self.assertIn('resume', res.data)

    def test_macro_document_is_rejected(self):
        res = self.apply(resume=resume_file(docx('word/vbaProject.bin'), 'cv.docx'))
        self.assertEqual(res.status_code, 400)
        self.assertIn('resume', res.data)

    def test_type_comes_from_the_content_not_from_the_name(self):
        res = self.apply(resume=resume_file(b'<html><script>alert(1)</script></html>', 'cv.pdf'))
        self.assertEqual(res.status_code, 400)
        self.assertIn('resume', res.data)
        self.assertFalse(VacancyApplication.objects.exists())

    def test_program_files_are_rejected(self):
        res = self.apply(resume=resume_file(b'MZ\x90\x00' + b'x' * 64, 'cv.exe', 'application/octet-stream'))
        self.assertEqual(res.status_code, 400)

    def test_big_file_is_rejected(self):
        res = self.apply(resume=resume_file(PDF + b'x' * RESUME_MAX_BYTES))
        self.assertEqual(res.status_code, 400)
        self.assertIn('resume', res.data)

    def test_empty_or_missing_file_is_rejected(self):
        self.assertEqual(self.apply(resume=resume_file(b'')).status_code, 400)
        payload = self.payload()
        del payload['resume']
        self.assertEqual(self.client.post(URL, payload, format='multipart').status_code, 400)

    def test_wrong_phone_is_rejected(self):
        for phone in ('12345', 'позвоните мне', '<script>'):
            with self.subTest(phone):
                res = self.apply(phone=phone)
                self.assertEqual(res.status_code, 400)
                self.assertIn('phone', res.data)

    def test_consent_is_required(self):
        res = self.apply(consent='false')
        self.assertEqual(res.status_code, 400)
        self.assertIn('consent', res.data)

    def test_closed_vacancy_takes_no_applications(self):
        res = self.apply(vacancy=str(self.closed_vacancy.pk))
        self.assertEqual(res.status_code, 400)
        self.assertIn('vacancy', res.data)

    def test_bot_filling_the_trap_is_not_saved(self):
        res = self.apply(website='http://spam.example')
        self.assertEqual(res.status_code, 201)
        self.assertFalse(VacancyApplication.objects.exists())

    def test_too_many_applications_from_one_address_are_stopped(self):
        statuses = [self.apply(phone=f'+996 700 000 0{index:02d}').status_code for index in range(12)]
        self.assertEqual(statuses[:10], [201] * 10)
        self.assertEqual(statuses[10:], [429, 429])

    def test_file_name_cannot_carry_path_or_quotes(self):
        self.assertEqual(self.apply(full_name='../"evil"/name').status_code, 201)
        self.assertEqual(VacancyApplication.objects.get().resume_name, 'Резюме ..  evil  name.pdf')


class ApplicationsAccessTests(ApplicationsTestCase):
    def test_personal_data_is_closed_to_visitors(self):
        application = self.application()
        for url in (URL, f'{URL}{application.pk}/', f'{URL}{application.pk}/resume/'):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.patch(f'{URL}{application.pk}/', {'status': 'hired'}).status_code, 401)
        self.assertEqual(self.client.delete(f'{URL}{application.pk}/').status_code, 401)

    def test_other_staff_cannot_read_applications(self):
        application = self.application()
        self.client.force_authenticate(self.content_manager)
        for url in (URL, f'{URL}{application.pk}/', f'{URL}{application.pk}/resume/'):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_list_has_no_file_inside(self):
        application = self.application()
        self.client.force_authenticate(self.hr)
        res = self.client.get(URL)

        self.assertEqual(res.status_code, 200)
        item = res.data['results'][0]
        self.assertEqual(item['id'], str(application.pk))
        self.assertEqual(item['status_label'], 'Новый')
        self.assertNotIn('resume_content', item)
        self.assertLess(len(res.content), 1000)

    def test_filter_by_status(self):
        self.application()
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(URL, {'status': 'new'}).data['count'], 1)
        self.assertEqual(self.client.get(URL, {'status': 'hired'}).data['count'], 0)

    def test_hr_downloads_the_file(self):
        application = self.application()
        self.client.force_authenticate(self.hr)
        res = self.client.get(f'{URL}{application.pk}/resume/')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, PDF)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertEqual(res['Cache-Control'], 'no-store')

    def test_hr_changes_only_status_and_note(self):
        application = self.application()
        self.client.force_authenticate(self.hr)
        res = self.client.patch(f'{URL}{application.pk}/', {
            'status': 'invited', 'hr_note': 'Собеседование в среду', 'full_name': 'Другой', 'phone': '0',
        }, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        application.refresh_from_db()
        self.assertEqual(application.status, 'invited')
        self.assertEqual(application.hr_note, 'Собеседование в среду')
        self.assertEqual(application.full_name, 'Асанов Бакыт')

    def test_unknown_status_is_rejected(self):
        application = self.application()
        self.client.force_authenticate(self.hr)
        res = self.client.patch(f'{URL}{application.pk}/', {'status': 'secret'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_hr_deletes_an_application(self):
        application = self.application()
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.delete(f'{URL}{application.pk}/').status_code, 204)
        self.assertFalse(VacancyApplication.objects.exists())

    def test_application_stays_when_the_vacancy_is_deleted(self):
        application = self.application()
        self.vacancy.delete()
        application.refresh_from_db()

        self.assertIsNone(application.vacancy)
        self.assertEqual(application.vacancy_title, 'Водитель')

    def test_wrong_id_gives_404(self):
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(f'{URL}not-a-uuid/').status_code, 404)
        self.assertEqual(self.client.get(f'{URL}not-a-uuid/resume/').status_code, 404)


class ApplicationsExportTests(ApplicationsTestCase):
    EXPORT = f'{URL}export/'

    def sheet(self):
        self.client.force_authenticate(self.hr)
        return load_workbook(BytesIO(self.client.get(self.EXPORT).content)).active

    def test_file_is_closed_to_everyone_but_hr(self):
        self.assertEqual(self.client.get(self.EXPORT).status_code, 401)
        self.client.force_authenticate(self.content_manager)
        self.assertEqual(self.client.get(self.EXPORT).status_code, 403)

    def test_hr_downloads_an_excel_file(self):
        self.client.force_authenticate(self.hr)
        res = self.client.get(self.EXPORT)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], XLSX_CONTENT_TYPE)
        self.assertIn('attachment; filename="otkliki-', res['Content-Disposition'])
        self.assertEqual(res['Cache-Control'], 'no-store')

    def test_row_has_all_data_of_the_application(self):
        application = self.application()
        application.status = 'invited'
        application.hr_note = 'Собеседование в среду'
        application.save()

        sheet = self.sheet()
        row = [cell.value for cell in sheet[FIRST_DATA_ROW]]

        self.assertEqual(sheet.cell(HEADER_ROW, 2).value, 'ФИО')
        self.assertEqual(row[1:6], ['Асанов Бакыт', '+996 700 123 456', 'bakyt@example.kg', 'Водитель', 'Приглашён'])
        self.assertEqual(row[6:8], ['Стаж 5 лет', 'Собеседование в среду'])
        self.assertEqual(row[0].date(), application.created_at.date())

    def test_summary_counts_all_and_new(self):
        self.application()
        VacancyApplication.objects.update(status='hired')
        self.apply(phone='+996 700 000 001')

        summary = self.sheet()['A2'].value
        self.assertIn('откликов: 2', summary)
        self.assertIn('новых: 1', summary)

    def test_all_statuses_get_into_the_file(self):
        self.application()
        VacancyApplication.objects.update(status='rejected')
        self.assertEqual(self.sheet().cell(FIRST_DATA_ROW, 6).value, 'Отказ')

    def test_text_from_candidates_never_becomes_a_formula(self):
        self.apply(full_name='=HYPERLINK("http://evil.example")', comment='=1+1')
        sheet = self.sheet()

        self.assertEqual(sheet.cell(FIRST_DATA_ROW, 2).data_type, 's')
        self.assertEqual(sheet.cell(FIRST_DATA_ROW, 7).data_type, 's')

    def test_long_comment_gets_a_taller_row(self):
        self.apply(comment='слово ' * 100)
        sheet = self.sheet()
        self.assertGreater(sheet.row_dimensions[FIRST_DATA_ROW].height, 60)

    def test_no_applications_still_gives_a_file(self):
        sheet = self.sheet()
        self.assertIn('откликов: 0', sheet['A2'].value)
        self.assertIsNone(sheet.cell(FIRST_DATA_ROW, 2).value)

    def test_export_is_not_mistaken_for_an_application_id(self):
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(self.EXPORT).status_code, 200)
        self.assertEqual(self.client.delete(self.EXPORT).status_code, 405)
