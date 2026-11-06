"""Общее оформление таблиц Excel для выгрузок из админки."""
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
MONEY_FORMAT = '#,##0.00'

NAVY = '102382'
INK = '1E293B'
MUTED = '64748B'
ZEBRA = 'F5F7FB'
LINE = 'D7DEEA'
TOTAL = 'E8F7EE'
GREEN = '15803D'

TITLE_ROW = 1
SUMMARY_ROW = 2
HEADER_ROW = 4
FIRST_DATA_ROW = HEADER_ROW + 1


def solid_fill(color):
    return PatternFill('solid', start_color=color, end_color=color)


def set_text(cell, value):
    """Значение от пользователя всегда остаётся текстом: «=...» не должно стать формулой при открытии файла"""
    cell.value = ILLEGAL_CHARACTERS_RE.sub('', str(value or ''))
    cell.data_type = 's'


def format_amount(value):
    return f'{value:,.2f}'.replace(',', ' ')


def today_text():
    return timezone.localdate().strftime('%d.%m.%Y')


def write_heading(sheet, columns, title_text, summary_text):
    last_column = get_column_letter(len(columns))
    sheet.merge_cells(f'A{TITLE_ROW}:{last_column}{TITLE_ROW}')
    sheet.merge_cells(f'A{SUMMARY_ROW}:{last_column}{SUMMARY_ROW}')

    title = sheet.cell(TITLE_ROW, 1, title_text)
    title.font = Font(name='Calibri', size=18, bold=True, color=NAVY)
    title.alignment = Alignment(vertical='center')
    sheet.row_dimensions[TITLE_ROW].height = 30

    summary = sheet.cell(SUMMARY_ROW, 1, summary_text)
    summary.font = Font(name='Calibri', size=11, color=MUTED)
    summary.alignment = Alignment(vertical='center')
    sheet.row_dimensions[SUMMARY_ROW].height = 20
    sheet.row_dimensions[HEADER_ROW - 1].height = 8


def write_header(sheet, columns):
    for index, (title, width, align) in enumerate(columns, start=1):
        cell = sheet.cell(HEADER_ROW, index, title)
        cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        cell.fill = solid_fill(NAVY)
        cell.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.row_dimensions[HEADER_ROW].height = 26


def style_row(sheet, row, columns, wrapped=()):
    """Оформляет строку данных; wrapped — ячейки с длинным текстом"""
    cells = [sheet.cell(row, index) for index in range(1, len(columns) + 1)]
    border = Border(bottom=Side(style='thin', color=LINE))
    for cell, (_, _, align) in zip(cells, columns):
        cell.font = Font(name='Calibri', size=11, color=INK)
        cell.alignment = Alignment(horizontal=align, vertical='center', wrap_text=cell in wrapped)
        cell.border = border
        if (row - FIRST_DATA_ROW) % 2:
            cell.fill = solid_fill(ZEBRA)
    sheet.row_dimensions[row].height = 21


def write_total(sheet, columns, last_data_row, total_columns):
    """Строка «Итого». total_columns: номер колонки -> формат числа"""
    row = last_data_row + 1
    border = Border(top=Side(style='medium', color=GREEN))
    for index in range(1, len(columns) + 1):
        cell = sheet.cell(row, index)
        cell.fill = solid_fill(TOTAL)
        cell.border = border
        cell.font = Font(name='Calibri', size=12, bold=True, color=GREEN)
        cell.alignment = Alignment(vertical='center')

    sheet.cell(row, 1, 'Итого')
    for column, number_format in total_columns.items():
        letter = get_column_letter(column)
        # SUBTOTAL: при включённом фильтре считает только видимые строки
        total = sheet.cell(row, column, f'=SUBTOTAL(109,{letter}{FIRST_DATA_ROW}:{letter}{last_data_row})')
        total.number_format = number_format
        total.alignment = Alignment(horizontal=columns[column - 1][2], vertical='center')
    sheet.row_dimensions[row].height = 24


def finish_sheet(sheet, columns, last_data_row):
    sheet.sheet_view.showGridLines = False
    if last_data_row >= FIRST_DATA_ROW:
        sheet.auto_filter.ref = f'A{HEADER_ROW}:{get_column_letter(len(columns))}{last_data_row}'

    # шапка таблицы видна при прокрутке и повторяется на каждом листе при печати
    sheet.freeze_panes = f'A{FIRST_DATA_ROW}'
    sheet.print_title_rows = f'{HEADER_ROW}:{HEADER_ROW}'
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.oddFooter.center.text = 'Страница &P из &N'


def xlsx_response(workbook, filename):
    buffer = BytesIO()
    workbook.save(buffer)
    return HttpResponse(
        buffer.getvalue(),
        content_type=XLSX_CONTENT_TYPE,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
