"""Выгрузки в Excel для админки: реестр закупок и отклики на вакансии."""
import math

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .excel import (
    FIRST_DATA_ROW,
    GREEN,
    HEADER_ROW,
    INK,
    MONEY_FORMAT,
    XLSX_CONTENT_TYPE,
    ZEBRA,
    finish_sheet,
    format_amount,
    set_text,
    solid_fill,
    style_row,
    today_text,
    write_header,
    write_heading,
    write_total,
    xlsx_response,
)
from .models import Procurement, VacancyApplication

__all__ = [
    'FIRST_DATA_ROW',
    'HEADER_ROW',
    'XLSX_CONTENT_TYPE',
    'applications_export_response',
    'build_applications_workbook',
    'build_procurements_workbook',
    'procurements_export',
]

# заголовок, ширина колонки, выравнивание
COLUMNS = [
    ('№', 8, 'center'),
    ('Номер контракта', 24, 'left'),
    ('Поставщик', 46, 'left'),
    ('Тип', 12, 'left'),
    ('Способ закупки', 30, 'left'),
    ('Статус', 14, 'center'),
    ('Дата', 13, 'center'),
    # с запасом: если сумма не помещается, Excel показывает ####
    ('Сумма, сом', 28, 'right'),
]
AMOUNT_COLUMN = len(COLUMNS)

# цвет текста и заливки статуса — как значки в админке
STATUS_COLORS = {
    'active': (GREEN, 'DCFCE7'),
    'completed': ('475569', 'E2E8F0'),
    'cancelled': ('B91C1C', 'FEE2E2'),
}


def _procurement_number(procurement):
    # числом: иначе Excel сортирует 10 раньше 2
    return int(procurement.number) if procurement.number.isdigit() else procurement.number


def _write_row(sheet, row, procurement):
    cells = [sheet.cell(row, index) for index in range(1, len(COLUMNS) + 1)]
    number, contract, supplier, kind, method, status, date, amount = cells

    number.value = _procurement_number(procurement)
    set_text(contract, procurement.contractNumber)
    set_text(supplier, procurement.supplier)
    set_text(kind, procurement.get_type_display())
    set_text(method, procurement.get_method_display())
    set_text(status, procurement.get_status_display())
    date.value = procurement.date
    date.number_format = 'DD.MM.YYYY'
    amount.value = procurement.amount
    amount.number_format = MONEY_FORMAT

    style_row(sheet, row, COLUMNS, wrapped=(supplier, method))
    supplier.font = Font(name='Calibri', size=11, bold=True, color=INK)
    amount.font = Font(name='Calibri', size=11, bold=True, color=INK)
    text_color, fill = STATUS_COLORS.get(procurement.status, (INK, ZEBRA))
    status.font = Font(name='Calibri', size=10, bold=True, color=text_color)
    status.fill = solid_fill(fill)


def build_procurements_workbook():
    procurements = list(Procurement.objects.all())
    total = sum((item.amount for item in procurements), start=0)

    workbook = Workbook()
    workbook.properties.title = 'Реестр закупок'
    workbook.properties.creator = 'МП «Тазалык»'
    sheet = workbook.active
    sheet.title = 'Закупки'

    write_heading(
        sheet,
        COLUMNS,
        'Реестр закупок МП «Тазалык»',
        f'Выгружено {today_text()}  ·  закупок: {len(procurements)}  ·  на сумму: {format_amount(total)} сом',
    )
    write_header(sheet, COLUMNS)

    for row, procurement in enumerate(procurements, start=FIRST_DATA_ROW):
        _write_row(sheet, row, procurement)

    last_data_row = FIRST_DATA_ROW + len(procurements) - 1
    if procurements:
        write_total(sheet, COLUMNS, last_data_row, {AMOUNT_COLUMN: MONEY_FORMAT})
    finish_sheet(sheet, COLUMNS, last_data_row)
    return workbook


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def procurements_export(request):
    """GET /api/procurements/export/ — все закупки файлом .xlsx"""
    return xlsx_response(build_procurements_workbook(), f'zakupki-{timezone.localdate():%Y-%m-%d}.xlsx')


# ========== ОТКЛИКИ НА ВАКАНСИИ ==========
APPLICATION_COLUMNS = [
    ('Дата отклика', 17, 'center'),
    ('ФИО', 34, 'left'),
    ('Телефон', 19, 'left'),
    ('Почта', 28, 'left'),
    ('Вакансия', 30, 'left'),
    ('Статус', 18, 'center'),
    ('Комментарий кандидата', 42, 'left'),
    ('Заметка отдела кадров', 42, 'left'),
]
LONG_TEXT_WIDTH = 42
LINE_HEIGHT = 15
BASE_ROW_HEIGHT = 21
# больше Excel не разрешает
MAX_ROW_HEIGHT = 409

# цвет текста и заливки статуса — как значки в админке
APPLICATION_STATUS_COLORS = {
    'new': ('1D4ED8', 'DBEAFE'),
    'in_review': ('B45309', 'FEF3C7'),
    'invited': (GREEN, 'DCFCE7'),
    'hired': ('475569', 'E2E8F0'),
    'rejected': ('B91C1C', 'FEE2E2'),
}


def _text_lines(text):
    return sum(max(1, math.ceil(len(line) / LONG_TEXT_WIDTH)) for line in (text or '').split('\n'))


def _write_application(sheet, row, application):
    cells = [sheet.cell(row, index) for index in range(1, len(APPLICATION_COLUMNS) + 1)]
    date, name, phone, email, vacancy, status, comment, note = cells

    # Excel не хранит часовой пояс, поэтому время — местное
    date.value = timezone.localtime(application.created_at).replace(tzinfo=None)
    date.number_format = 'DD.MM.YYYY HH:MM'
    set_text(name, application.full_name)
    set_text(phone, application.phone)
    set_text(email, application.email)
    set_text(vacancy, application.vacancy_title)
    set_text(status, application.get_status_display())
    set_text(comment, application.comment)
    set_text(note, application.hr_note)

    style_row(sheet, row, APPLICATION_COLUMNS, wrapped=(name, vacancy, comment, note))
    name.font = Font(name='Calibri', size=11, bold=True, color=INK)
    text_color, fill = APPLICATION_STATUS_COLORS.get(application.status, (INK, ZEBRA))
    status.font = Font(name='Calibri', size=10, bold=True, color=text_color)
    status.fill = solid_fill(fill)

    # длинный комментарий не должен обрезаться высотой строки
    lines = max(_text_lines(application.comment), _text_lines(application.hr_note))
    sheet.row_dimensions[row].height = min(max(BASE_ROW_HEIGHT, lines * LINE_HEIGHT), MAX_ROW_HEIGHT)


def build_applications_workbook():
    applications = list(VacancyApplication.objects.defer('resume_content'))
    new_count = sum(item.status == 'new' for item in applications)

    workbook = Workbook()
    workbook.properties.title = 'Отклики на вакансии'
    workbook.properties.creator = 'МП «Тазалык»'
    sheet = workbook.active
    sheet.title = 'Отклики'

    write_heading(
        sheet,
        APPLICATION_COLUMNS,
        'Отклики на вакансии МП «Тазалык»',
        f'Выгружено {today_text()}  ·  откликов: {len(applications)}  ·  новых: {new_count}',
    )
    write_header(sheet, APPLICATION_COLUMNS)

    for row, application in enumerate(applications, start=FIRST_DATA_ROW):
        _write_application(sheet, row, application)

    finish_sheet(sheet, APPLICATION_COLUMNS, FIRST_DATA_ROW + len(applications) - 1)
    return workbook


def applications_export_response():
    response = xlsx_response(build_applications_workbook(), f'otkliki-{timezone.localdate():%Y-%m-%d}.xlsx')
    # личные данные не должны оставаться в кэше браузера и прокси
    response['Cache-Control'] = 'no-store'
    return response
