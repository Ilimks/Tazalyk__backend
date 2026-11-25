"""Поиск по спискам админки: ?search=строка

Слова ищутся все сразу («строй бишкек» найдёт «Бишкек Строй Сервис»), регистр не важен.
Телефон находится в любом виде: «0700 123 456» и «700123456» найдут «+996 (700) 12-34-56».
"""
import re

from django.db.models import Q
from rest_framework import filters

# строка поиска приходит и от посетителей сайта: длинные запросы незачем, а базу они нагружают
MAX_LENGTH = 100
MAX_WORDS = 6
# короче — почти любой телефон подойдёт
MIN_PHONE_DIGITS = 4


def search_words(value):
    value = value.replace('\x00', ' ').replace('№', ' ')[:MAX_LENGTH]
    return value.split()[:MAX_WORDS]


def phone_digits(value):
    """Цифры телефона без кода страны и ведущего нуля; None — это не похоже на телефон"""
    if not re.fullmatch(r'[\d\s()+\-.]+', value.strip()):
        return None
    digits = re.sub(r'\D', '', value)
    if digits.startswith('996') and len(digits) > 9:
        digits = digits[3:]
    elif digits.startswith('0') and len(digits) >= 9:
        digits = digits[1:]
    return digits if len(digits) >= MIN_PHONE_DIGITS else None


class ListSearchFilter(filters.BaseFilterBackend):
    """Поля задаёт раздел: search_text — текст, search_phone — телефоны"""

    def filter_queryset(self, request, queryset, view):
        value = request.query_params.get('search', '')
        words = search_words(value)
        if not words:
            return queryset

        phone_fields = getattr(view, 'search_phone', ())
        # телефон целиком: между цифрами в базе могут стоять скобки, пробелы и дефисы
        digits = phone_digits(' '.join(words)) if phone_fields else None
        by_phone = Q()
        if digits:
            pattern = '[^0-9]*'.join(digits)
            for field in phone_fields:
                by_phone |= Q(**{f'{field}__regex': pattern})

        by_text = Q()
        for word in words:
            matches = Q()
            for field in view.search_text:
                matches |= Q(**{f'{field}__icontains': word})
            by_text &= matches

        queryset = queryset.filter(by_text | by_phone if digits else by_text)
        # поиск по товарам заказа соединяет таблицы: заказ с двумя подходящими товарами нужен один раз
        return queryset.distinct() if any('__' in field for field in view.search_text) else queryset
