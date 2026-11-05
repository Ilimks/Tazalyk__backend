"""Поиск по сайту: новости, товары, вакансии, документы и закупки.

Ищет сразу на русском и кыргызском, что бы ни было выбрано на сайте. Запрос прощает окончания,
буквы без кыргызских знаков (жанылык → жаңылык) и английскую раскладку (yjdjcnb → новости).
Те же правила для текстов страниц — на сайте, в features/site-search/lib/text.ts.
"""
import re

from django.db.models import Case, Func, IntegerField, Q, TextField, Value, When
from django.db.models.functions import Coalesce, Concat, Lower
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from shop.models import Product

from .models import Legislation, LocalAct, News, Procurement, Vacancy

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 100
MAX_TOKENS = 6
DEFAULT_LIMIT = 5
MAX_LIMIT = 20
SNIPPET_LENGTH = 140
SNIPPET_LEAD = 40

KYRGYZ_FROM = 'ёөүң'
KYRGYZ_TO = 'еоун'
NORMALIZE_TABLE = str.maketrans(KYRGYZ_FROM, KYRGYZ_TO)
LATIN_LAYOUT = str.maketrans(
    "`qwertyuiop[]asdfghjkl;'zxcvbnm,.",
    'ёйцукенгшщзхъфывапролджэячсмитьбю',
)
WORD_CHARS = 'а-яa-z0-9'
TOKEN_RE = re.compile(f'[{WORD_CHARS}]+')
LATIN_RE = re.compile('[a-z]')
CYRILLIC_RE = re.compile('[а-я]')


def normalize(text):
    """Регистр и буквы приводятся к одному виду. Длина строки не меняется: на этом держится поиск отрывка"""
    return text.lower().translate(NORMALIZE_TABLE)


def stem(token):
    """Основа слова: окончания в запросе и в тексте могут отличаться (контейнеров → контейнер, таштандыларды → таштанды)"""
    length = len(token)
    if token.isdigit() or length <= 4:
        return token
    if length == 5:
        return token[:-1]
    if length <= 7:
        return token[:-2]
    return token[:int(length * 0.65 + 0.5)]


def query_variants(query):
    """Варианты запроса в виде списков основ: сам запрос и, если он набран латиницей, он же в русской раскладке"""
    text = normalize(query)
    variants = [text]
    if LATIN_RE.search(text) and not CYRILLIC_RE.search(text):
        variants.append(normalize(text.translate(LATIN_LAYOUT)))

    stems = []
    for variant in variants:
        tokens = TOKEN_RE.findall(variant)[:MAX_TOKENS]
        if tokens:
            stems.append([stem(token) for token in tokens])
    return stems


class Normalized(Func):
    """normalize() на стороне базы"""

    function = 'translate'
    output_field = TextField()

    def __init__(self, expression):
        super().__init__(Lower(expression), Value(KYRGYZ_FROM), Value(KYRGYZ_TO))


def _haystack(fields):
    parts = []
    for field in fields:
        parts += [Coalesce(field, Value(''), output_field=TextField()), Value(' ')]
    return Normalized(Concat(*parts, output_field=TextField()))


def _matches(alias, variants):
    """Подходит любой вариант запроса; внутри варианта должны найтись все слова, с начала слова"""
    any_variant = Q()
    for stems in variants:
        all_words = Q()
        for word in stems:
            all_words &= Q(**{f'{alias}__regex': f'(^|[^{WORD_CHARS}]){word}'})
        any_variant |= all_words
    return any_variant


def _snippet(text, variants):
    """Отрывок вокруг найденного слова; без совпадения — начало текста"""
    flat = ' '.join((text or '').split())
    if not flat:
        return ''

    hay = normalize(flat)
    found = [
        match.start(1)
        for stems in variants
        for word in stems
        for match in [re.search(f'(?:^|[^{WORD_CHARS}])({word})', hay)]
        if match
    ]
    start = 0
    if found:
        start = max(min(found) - SNIPPET_LEAD, 0)
        if start:
            # отрывок начинается с целого слова
            start = flat.find(' ', start) + 1

    end = start + SNIPPET_LENGTH
    piece = flat[start:end].rstrip()
    return f"{'…' if start else ''}{piece}{'…' if end < len(flat) else ''}"


def _search(queryset, title_fields, text_fields, variants, limit, ordering, columns):
    """Только нужные текстовые колонки: файлы в base64 сюда не попадают"""
    return list(
        queryset
        .annotate(search_title=_haystack(title_fields), search_all=_haystack(title_fields + text_fields))
        .filter(_matches('search_all', variants))
        .annotate(in_title=Case(
            When(_matches('search_title', variants), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ))
        .order_by('-in_title', *ordering)
        .values('id', 'in_title', *columns)[:limit]
    )


def _item(kind, row, title_ru, title_ky=None, snippet_ru='', snippet_ky='', date=None):
    return {
        'type': kind,
        'id': str(row['id']),
        'title_ru': title_ru,
        'title_ky': title_ky or title_ru,
        'snippet_ru': snippet_ru,
        'snippet_ky': snippet_ky or snippet_ru,
        'date': date.isoformat() if date else None,
        'in_title': bool(row['in_title']),
    }


def _find_news(variants, limit):
    rows = _search(
        News.objects.all(), ['title_ru', 'title_ky'], ['description_ru', 'description_ky'], variants, limit,
        ['-date', '-created_at'], ['title_ru', 'title_ky', 'description_ru', 'description_ky', 'date'],
    )
    return [
        _item(
            'news', row, row['title_ru'], row['title_ky'],
            _snippet(row['description_ru'], variants), _snippet(row['description_ky'], variants), row['date'],
        )
        for row in rows
    ]


def _find_products(variants, limit):
    rows = _search(
        Product.objects.filter(is_active=True), ['name_ru', 'name_ky'], ['description_ru', 'description_ky'],
        variants, limit, ['sort_order'], ['name_ru', 'name_ky', 'description_ru', 'description_ky'],
    )
    return [
        _item(
            'product', row, row['name_ru'], row['name_ky'],
            _snippet(row['description_ru'], variants), _snippet(row['description_ky'], variants),
        )
        for row in rows
    ]


def _find_vacancies(variants, limit):
    texts = ['description_ru', 'description_ky', 'requirements_ru', 'requirements_ky']
    rows = _search(
        Vacancy.objects.filter(is_active=True), ['title_ru', 'title_ky'], texts, variants, limit,
        ['-created_at'], ['title_ru', 'title_ky', *texts],
    )
    return [
        _item(
            'vacancy', row, row['title_ru'], row['title_ky'],
            _snippet(f"{row['description_ru']} {row['requirements_ru']}", variants),
            _snippet(f"{row['description_ky']} {row['requirements_ky']}", variants),
        )
        for row in rows
    ]


def _find_documents(model, kind, variants, limit):
    rows = _search(
        model.objects.all(), ['title'], ['file_name'], variants, limit, ['-date', '-created_at'], ['title', 'date'],
    )
    return [_item(kind, row, row['title'], date=row['date']) for row in rows]


def _find_procurements(variants, limit):
    rows = _search(
        Procurement.objects.all(), ['supplier'], ['contractNumber', 'number'], variants, limit,
        ['-date', '-created_at'], ['supplier', 'contractNumber', 'date'],
    )
    return [_item('procurement', row, row['supplier'], snippet_ru=row['contractNumber'], date=row['date']) for row in rows]


class SearchView(APIView):
    """GET /api/search/?q=запрос&limit=5 — limit считается на каждый раздел"""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'search'

    def get(self, request):
        query = request.query_params.get('q', '').strip()[:MAX_QUERY_LENGTH]
        variants = query_variants(query) if len(query) >= MIN_QUERY_LENGTH else []
        if not variants:
            return Response({'results': []})

        try:
            limit = min(max(int(request.query_params.get('limit', DEFAULT_LIMIT)), 1), MAX_LIMIT)
        except ValueError:
            limit = DEFAULT_LIMIT

        return Response({
            'results': [
                *_find_news(variants, limit),
                *_find_products(variants, limit),
                *_find_vacancies(variants, limit),
                *_find_documents(LocalAct, 'local_act', variants, limit),
                *_find_documents(Legislation, 'legislation', variants, limit),
                *_find_procurements(variants, limit),
            ],
        })
