"""Поиск по сайту: оба языка, окончания, кыргызские буквы, раскладка и то, что наружу не попадает."""
import json
from unittest import mock

from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from shop.models import Product

from .models import Legislation, LocalAct, News, Procurement, Vacancy
from .search import query_variants, stem


class SearchTextTests(APITestCase):
    def test_stem_keeps_the_start_of_a_word(self):
        self.assertEqual(stem('контейнеров'), 'контейн')
        self.assertEqual(stem('контейнер'), 'контей')
        self.assertEqual(stem('таштандыларды'), 'таштанды')
        self.assertEqual(stem('акт'), 'акт')
        self.assertEqual(stem('2026'), '2026')

    def test_latin_query_also_tries_russian_layout(self):
        self.assertEqual(query_variants('yjdjcnb'), [['yjdjc'], ['новос']])
        self.assertEqual(query_variants('новости'), [['новос']])


class SearchApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.news = News.objects.create(
            title_ru='Новые мусорные контейнеры в Бишкеке',
            title_ky='Бишкекте жаңы таштанды контейнерлери',
            description_ru='Предприятие установило контейнеры во дворах.',
            description_ky='Ишкана короолорго контейнерлерди орнотту.',
            image='data:image/jpeg;base64,/9j/SECRETBASE64',
            date='2026-05-22',
        )
        cls.other = News.objects.create(
            title_ru='Субботник', title_ky='Ишембилик', description_ru='Уборка парка и контейнеры.', date='2026-05-23',
        )
        Product.objects.create(
            name_ru='Контейнер пластиковый', name_ky='Пластик контейнер', volume=240, material='plastic', price=1200,
        )
        Product.objects.create(name_ru='Скрытый контейнер', volume=240, material='plastic', price=1, is_active=False)
        Vacancy.objects.create(title_ru='Водитель мусоровоза', title_ky='Таштанды ташуучу айдоочу', is_active=True)
        Vacancy.objects.create(title_ru='Водитель архивный', is_active=False)
        LocalAct.objects.create(title='Положение о закупках', file_url='data:application/pdf;base64,JVBERiSECRET', date='2026-01-01')
        Legislation.objects.create(title='Закон о местном самоуправлении', file_url='/x.pdf', date='2026-01-01')
        Procurement.objects.create(contractNumber='К-77/2026', supplier='ОсОО Чистый город', amount=100, date='2026-02-01')

    def setUp(self):
        cache.clear()

    def find(self, query, **params):
        res = self.client.get('/api/search/', {'q': query, **params})
        self.assertEqual(res.status_code, 200)
        return res.data['results']

    def types(self, query):
        return [item['type'] for item in self.find(query)]

    def test_russian_query_finds_kyrgyz_and_russian_titles_of_the_same_news(self):
        for query in ('контейнеры', 'контейнерлери', 'жаңы таштанды'):
            self.assertIn(str(self.news.id), [item['id'] for item in self.find(query)], query)

    def test_both_languages_are_returned(self):
        item = next(i for i in self.find('таштанды') if i['type'] == 'news')
        self.assertEqual(item['title_ru'], 'Новые мусорные контейнеры в Бишкеке')
        self.assertEqual(item['title_ky'], 'Бишкекте жаңы таштанды контейнерлери')

    def test_kyrgyz_letters_can_be_typed_as_russian(self):
        self.assertIn('news', self.types('жаны'))
        self.assertIn('news', self.types('ЖАҢЫ'))

    def test_endings_do_not_matter(self):
        self.assertIn('news', self.types('контейнеров'))
        self.assertIn('vacancy', self.types('водителя'))

    def test_wrong_keyboard_layout(self):
        self.assertIn('news', self.types('rjyntqyth'))

    def test_all_words_must_be_present(self):
        self.assertIn('news', self.types('контейнеры бишкек'))
        self.assertNotIn('news', self.types('контейнеры ташкент'))

    def test_match_starts_at_the_beginning_of_a_word(self):
        # «акт» не должно находиться внутри другого слова
        self.assertEqual(self.find('нтейн'), [])

    def test_title_matches_come_first(self):
        items = [i for i in self.find('контейнеры') if i['type'] == 'news']
        self.assertEqual([i['in_title'] for i in items], [True, False])

    def test_every_section_is_searched(self):
        self.assertIn('product', self.types('пластиковый'))
        self.assertIn('vacancy', self.types('мусоровоза'))
        self.assertIn('local_act', self.types('положение'))
        self.assertIn('legislation', self.types('самоуправлении'))
        self.assertIn('procurement', self.types('чистый город'))
        self.assertIn('procurement', self.types('К-77'))

    def test_hidden_records_are_not_found(self):
        self.assertEqual([i for i in self.find('скрытый')], [])
        self.assertEqual([i for i in self.find('архивный')], [])

    def test_files_never_reach_the_response(self):
        body = json.dumps(self.find('контейнеры') + self.find('положение'))
        self.assertNotIn('SECRET', body)
        self.assertNotIn('base64', body)

    def test_snippet_shows_the_found_word(self):
        item = next(i for i in self.find('дворах') if i['type'] == 'news')
        self.assertIn('дворах', item['snippet_ru'])

    def test_empty_and_short_queries_return_nothing(self):
        self.assertEqual(self.find(''), [])
        self.assertEqual(self.find('к'), [])
        self.assertEqual(self.find('!!!'), [])

    def test_regex_characters_are_harmless(self):
        self.assertEqual(self.find("(контейн*[' OR 1=1 --"), self.find("контейн OR 1 1"))

    def test_limit_is_capped(self):
        News.objects.bulk_create(
            News(title_ru=f'Контейнер {i}', description_ru='', date='2026-01-01') for i in range(30)
        )
        news = [i for i in self.find('контейнер', limit=500) if i['type'] == 'news']
        self.assertEqual(len(news), 20)
        self.assertLessEqual(len([i for i in self.find('контейнер', limit='abc') if i['type'] == 'news']), 5)

    def test_search_is_rate_limited(self):
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'search': '2/min'}):
            codes = [self.client.get('/api/search/', {'q': 'контейнер'}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
