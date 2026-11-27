import re

from django.db.models import Q
from rest_framework import filters

MAX_LENGTH = 100
MAX_WORDS = 6
MIN_PHONE_DIGITS = 4


def search_words(value):
    value = value.replace('\x00', ' ').replace('№', ' ')[:MAX_LENGTH]
    return value.split()[:MAX_WORDS]


def phone_digits(value):
    if not re.fullmatch(r'[\d\s()+\-.]+', value.strip()):
        return None
    digits = re.sub(r'\D', '', value)
    if digits.startswith('996') and len(digits) > 9:
        digits = digits[3:]
    elif digits.startswith('0') and len(digits) >= 9:
        digits = digits[1:]
    return digits if len(digits) >= MIN_PHONE_DIGITS else None


class ListSearchFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        value = request.query_params.get('search', '')
        words = search_words(value)
        if not words:
            return queryset

        phone_fields = getattr(view, 'search_phone', ())
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
        return queryset.distinct() if any('__' in field for field in view.search_text) else queryset
