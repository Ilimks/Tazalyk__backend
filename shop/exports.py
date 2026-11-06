"""Выгрузка проданных и отклонённых товаров в Excel для админки."""
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font

from api.excel import (
    FIRST_DATA_ROW,
    INK,
    MONEY_FORMAT,
    finish_sheet,
    format_amount,
    set_text,
    style_row,
    today_text,
    write_header,
    write_heading,
    write_total,
    xlsx_response,
)

from .models import OrderItem

# заказы в работе (новые и ожидающие оплаты) в выгрузку не входят: их судьба ещё не решена
SOLD_STATUSES = ('paid', 'completed')
REJECTED_STATUSES = ('cancelled',)

# заголовок, ширина колонки, выравнивание
COLUMNS = [
    ('№ заказа', 10, 'center'),
    ('Дата заказа', 13, 'center'),
    ('Товар', 40, 'left'),
    ('Объём, л', 10, 'center'),
    ('Кол-во', 9, 'center'),
    ('Цена, сом', 18, 'right'),
    ('Сумма, сом', 22, 'right'),
    ('Покупатель', 28, 'left'),
    ('Телефон', 19, 'left'),
    ('Получение', 13, 'left'),
    ('Статус', 12, 'center'),
]
QUANTITY_COLUMN = 5
AMOUNT_COLUMN = 7


def _write_row(sheet, row, item):
    order = item.order
    cells = [sheet.cell(row, index) for index in range(1, len(COLUMNS) + 1)]
    number, date, name, volume, quantity, price, amount, customer, phone, delivery, status = cells

    number.value = order.id
    # Excel не хранит часовой пояс, поэтому дата — местная, без времени
    date.value = timezone.localtime(order.created_at).date()
    date.number_format = 'DD.MM.YYYY'
    set_text(name, item.product_name)
    volume.value = item.volume
    quantity.value = item.quantity
    price.value = item.price
    price.number_format = MONEY_FORMAT
    amount.value = item.subtotal
    amount.number_format = MONEY_FORMAT
    set_text(customer, order.customer_name)
    set_text(phone, order.phone)
    set_text(delivery, order.get_delivery_method_display())
    set_text(status, order.get_status_display())

    style_row(sheet, row, COLUMNS, wrapped=(name, customer))
    amount.font = Font(name='Calibri', size=11, bold=True, color=INK)


def _write_sheet(sheet, title, statuses):
    items = list(
        OrderItem.objects
        .filter(order__status__in=statuses)
        .select_related('order')
        .order_by('-order__created_at', 'id')
    )
    pieces = sum(item.quantity for item in items)
    total = sum((item.subtotal for item in items), start=0)

    write_heading(
        sheet,
        COLUMNS,
        title,
        f'Выгружено {today_text()}  ·  товаров: {pieces} шт.  ·  на сумму: {format_amount(total)} сом',
    )
    write_header(sheet, COLUMNS)

    for row, item in enumerate(items, start=FIRST_DATA_ROW):
        _write_row(sheet, row, item)

    last_data_row = FIRST_DATA_ROW + len(items) - 1
    if items:
        write_total(sheet, COLUMNS, last_data_row, {QUANTITY_COLUMN: '0', AMOUNT_COLUMN: MONEY_FORMAT})
    finish_sheet(sheet, COLUMNS, last_data_row)


def build_orders_workbook():
    """Два листа: суммы проданного и отклонённого нельзя складывать в один итог"""
    workbook = Workbook()
    workbook.properties.title = 'Проданные и отклонённые товары'
    workbook.properties.creator = 'МП «Тазалык»'

    sold = workbook.active
    sold.title = 'Продано'
    _write_sheet(sold, 'Проданные товары МП «Тазалык»', SOLD_STATUSES)
    _write_sheet(workbook.create_sheet('Отклонено'), 'Отклонённые товары МП «Тазалык»', REJECTED_STATUSES)
    return workbook


def orders_export_response():
    return xlsx_response(build_orders_workbook(), f'zakazy-{timezone.localdate():%Y-%m-%d}.xlsx')
