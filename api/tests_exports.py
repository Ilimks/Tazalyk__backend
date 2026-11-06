"""Выгрузка закупок в Excel: доступ, полнота данных, оформление и защита от формул."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from .exports import FIRST_DATA_ROW, HEADER_ROW, XLSX_CONTENT_TYPE
from .models import Procurement


class ProcurementExportTests(APITestCase):
    URL = '/api/procurements/export/'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('viewer_test', password='x')
        Procurement.objects.create(
            contractNumber='К-1', supplier='ОсОО Чистый город', type='goods', method='tender',
            status='completed', date='2026-01-10', amount=Decimal('1500.50'),
        )
        Procurement.objects.create(
            contractNumber='0012', supplier='=HYPERLINK("http://evil.example")', type='works', method='simple',
            status='active', date='2026-02-20', amount=Decimal('2000.25'),
        )

    def download(self):
        self.client.force_authenticate(self.user)
        return self.client.get(self.URL)

    def sheet(self):
        return load_workbook(BytesIO(self.download().content)).active

    def test_login_is_required(self):
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_download_is_an_excel_file(self):
        res = self.download()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], XLSX_CONTENT_TYPE)
        self.assertIn('attachment; filename="zakupki-', res['Content-Disposition'])

    def test_all_records_are_exported_newest_first_with_readable_labels(self):
        sheet = self.sheet()
        self.assertEqual(sheet.cell(HEADER_ROW, 3).value, 'Поставщик')
        newest = [cell.value for cell in sheet[FIRST_DATA_ROW]]
        self.assertEqual(newest[1], '0012')
        self.assertEqual(newest[3:6], ['Работа', 'Простейшая закупка', 'Активна'])
        self.assertEqual(newest[6].date(), date(2026, 2, 20))
        self.assertEqual(Decimal(str(newest[7])), Decimal('2000.25'))
        oldest = [cell.value for cell in sheet[FIRST_DATA_ROW + 1]]
        self.assertEqual(oldest[2], 'ОсОО Чистый город')
        self.assertEqual(oldest[4], 'Конкурс')

    def test_number_is_stored_as_a_number_for_sorting(self):
        self.assertIsInstance(self.sheet().cell(FIRST_DATA_ROW, 1).value, int)

    def test_supplier_text_never_becomes_a_formula(self):
        cell = self.sheet().cell(FIRST_DATA_ROW, 3)
        self.assertEqual(cell.value, '=HYPERLINK("http://evil.example")')
        self.assertEqual(cell.data_type, 's')

    def test_total_row_sums_amounts_and_respects_filters(self):
        sheet = self.sheet()
        total_row = FIRST_DATA_ROW + 2
        self.assertEqual(sheet.cell(total_row, 1).value, 'Итого')
        self.assertEqual(
            sheet.cell(total_row, 8).value,
            f'=SUBTOTAL(109,H{FIRST_DATA_ROW}:H{FIRST_DATA_ROW + 1})',
        )

    def test_sheet_is_ready_for_work_and_printing(self):
        sheet = self.sheet()
        self.assertEqual(sheet.freeze_panes, f'A{FIRST_DATA_ROW}')
        self.assertEqual(sheet.auto_filter.ref, f'A{HEADER_ROW}:H{FIRST_DATA_ROW + 1}')
        self.assertEqual(sheet.page_setup.orientation, 'landscape')

    def test_summary_shows_count_and_amount(self):
        self.assertIn('закупок: 2', self.sheet().cell(2, 1).value)
        self.assertIn('3 500.75', self.sheet().cell(2, 1).value)

    def test_empty_registry_still_downloads(self):
        Procurement.objects.all().delete()
        self.assertEqual(self.download().status_code, 200)
