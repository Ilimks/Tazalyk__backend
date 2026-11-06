"""Выгрузка заказов в Excel: доступ, какие товары попадают в файл, суммы, безопасность значений."""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from api.excel import FIRST_DATA_ROW, XLSX_CONTENT_TYPE

from .exports import AMOUNT_COLUMN, QUANTITY_COLUMN
from .models import Order, OrderItem


def make_order(status, customer='Айбек', items=(('Контейнер 240 л', 240, '5000.50', 2),), **extra):
    total = sum(Decimal(price) * quantity for _, _, price, quantity in items)
    order = Order.objects.create(
        customer_name=customer, phone='+996700123456', delivery_method='pickup',
        status=status, total=total, **extra,
    )
    for name, volume, price, quantity in items:
        OrderItem.objects.create(order=order, product_name=name, volume=volume, price=Decimal(price), quantity=quantity)
    return order


class OrdersExportTests(APITestCase):
    URL = '/api/shop/orders/export/'

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_superuser('shop_boss', password='x')
        cls.visitor = User.objects.create_user('visitor', password='x')
        cls.completed = make_order('completed', items=(
            ('Контейнер 240 л', 240, '5000.50', 2),
            ('Контейнер 120 л', 120, '3000.00', 1),
        ))
        cls.paid = make_order('paid', customer='Гүлзат')
        cls.cancelled = make_order('cancelled', customer='Нурлан', items=(('Бак 1100 л', 1100, '25000.00', 3),))
        make_order('new', customer='Новый покупатель')
        make_order('awaiting_payment', customer='Ждёт оплаты')

    def workbook(self):
        self.client.force_authenticate(self.manager)
        return load_workbook(BytesIO(self.client.get(self.URL).content))

    def rows(self, sheet):
        data = []
        for row in sheet.iter_rows(min_row=FIRST_DATA_ROW, values_only=True):
            if row[0] == 'Итого':
                break
            data.append(row)
        return data

    def test_visitors_cannot_download(self):
        self.assertEqual(self.client.get(self.URL).status_code, 401)
        self.client.force_authenticate(self.visitor)
        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_manager_gets_an_excel_file(self):
        self.client.force_authenticate(self.manager)
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], XLSX_CONTENT_TYPE)
        self.assertIn('attachment', res['Content-Disposition'])

    def test_export_is_not_mistaken_for_an_order_number(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get(self.URL).status_code, 200)
        self.assertEqual(self.client.get(f'/api/shop/orders/{self.paid.id}/').status_code, 200)

    def test_sold_sheet_has_paid_and_completed_items_only(self):
        rows = self.rows(self.workbook()['Продано'])

        self.assertEqual(sorted(row[2] for row in rows), ['Контейнер 120 л', 'Контейнер 240 л', 'Контейнер 240 л'])
        self.assertEqual({row[0] for row in rows}, {self.completed.id, self.paid.id})
        self.assertEqual({row[10] for row in rows}, {'Выполнен', 'Оплачен'})

    def test_rejected_sheet_has_cancelled_items_only(self):
        rows = self.rows(self.workbook()['Отклонено'])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], self.cancelled.id)
        self.assertEqual(rows[0][2], 'Бак 1100 л')
        self.assertEqual(rows[0][10], 'Отменён')

    def test_orders_in_progress_are_left_out(self):
        workbook = self.workbook()
        customers = {row[7] for sheet in workbook for row in self.rows(sheet)}

        self.assertNotIn('Новый покупатель', customers)
        self.assertNotIn('Ждёт оплаты', customers)

    def test_each_row_is_one_product_with_its_amount(self):
        rows = self.rows(self.workbook()['Продано'])
        row = next(row for row in rows if row[2] == 'Контейнер 120 л')

        self.assertEqual(row[3], 120)
        self.assertEqual(row[4], 1)
        self.assertEqual(row[5], 3000)
        self.assertEqual(row[6], 3000)
        self.assertEqual(row[7], 'Айбек')
        self.assertEqual(row[9], 'Самовывоз')

    def test_summary_counts_pieces_and_money_of_its_own_sheet(self):
        workbook = self.workbook()
        # 2 + 1 + 2 штуки: 10001 + 3000 + 10001 сом
        self.assertIn('товаров: 5 шт.', workbook['Продано']['A2'].value)
        self.assertIn('23 002.00 сом', workbook['Продано']['A2'].value)
        self.assertIn('товаров: 3 шт.', workbook['Отклонено']['A2'].value)
        self.assertIn('75 000.00 сом', workbook['Отклонено']['A2'].value)

    def test_total_row_counts_quantity_and_amount(self):
        sheet = self.workbook()['Продано']
        total_row = next(row for row in sheet.iter_rows() if row[0].value == 'Итого')

        self.assertTrue(total_row[QUANTITY_COLUMN - 1].value.startswith('=SUBTOTAL(109,E'))
        self.assertTrue(total_row[AMOUNT_COLUMN - 1].value.startswith('=SUBTOTAL(109,G'))

    def test_text_from_buyers_never_becomes_a_formula(self):
        make_order('completed', customer='=HYPERLINK("http://evil.example")')
        sheet = self.workbook()['Продано']
        cell = next(row[7] for row in sheet.iter_rows(min_row=FIRST_DATA_ROW) if str(row[7].value).startswith('='))

        self.assertEqual(cell.data_type, 's')

    def test_item_of_a_deleted_product_is_kept(self):
        rows = self.rows(self.workbook()['Отклонено'])
        self.assertIsNone(OrderItem.objects.get(order=self.cancelled).product)
        self.assertEqual(rows[0][2], 'Бак 1100 л')

    def test_empty_shop_still_gives_a_correct_file(self):
        Order.objects.all().delete()
        workbook = self.workbook()

        self.assertEqual(workbook.sheetnames, ['Продано', 'Отклонено'])
        self.assertEqual(self.rows(workbook['Продано']), [])
        self.assertIn('товаров: 0 шт.', workbook['Отклонено']['A2'].value)
