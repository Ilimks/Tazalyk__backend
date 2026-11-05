import base64
import json
import shutil
import tempfile
from decimal import Decimal
from unittest import mock
from urllib.parse import unquote

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from .contacts import international_phone
from .models import Order, Product

# минимальный настоящий PNG 1×1
PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
)
PNG_DATA_URL = 'data:image/png;base64,' + base64.b64encode(PNG_1PX).decode()

MEDIA_DIR = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=MEDIA_DIR,
    PUBLIC_MEDIA_BASE_URL='',
    SHOP_TELEGRAM_USERNAME='tazalyk_shop',
    SHOP_WHATSAPP_PHONE='+996 700 111 222',
)
class ShopApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.p240 = Product.objects.create(name_ru='Контейнер 240', volume=240, material='plastic', price=Decimal('3500'))
        self.p1100 = Product.objects.create(
            name_ru='Евроконтейнер 1100', volume=1100, material='galvanized', price=Decimal('25000'), is_featured=True,
        )
        self.hidden = Product.objects.create(name_ru='Скрытый', volume=120, material='plastic', price=1, is_active=False)
        self.out = Product.objects.create(name_ru='Нет в наличии', volume=660, material='metal', price=9000, in_stock=False)

        self.manager = User.objects.create_user('shop_manager', password='x')
        self.manager.groups.add(Group.objects.get(name='shop_managers'))
        self.content = User.objects.create_user('content_manager', password='x')

    # ---------- каталог ----------
    def test_public_list_hides_inactive(self):
        res = self.client.get('/api/shop/products/')
        self.assertEqual(res.status_code, 200)
        names = {p['name_ru'] for p in res.data['results']}
        self.assertNotIn('Скрытый', names)
        self.assertEqual(res.data['count'], 3)

    def test_filters_and_ordering(self):
        res = self.client.get('/api/shop/products/?volume=240,1100&material=plastic,galvanized&ordering=-price')
        self.assertEqual([p['volume'] for p in res.data['results']], [1100, 240])
        res = self.client.get('/api/shop/products/?price_min=5000&price_max=10000')
        self.assertEqual([p['name_ru'] for p in res.data['results']], ['Нет в наличии'])
        res = self.client.get('/api/shop/products/?in_stock=1')
        self.assertEqual(res.data['count'], 2)
        res = self.client.get('/api/shop/products/?featured=1')
        self.assertEqual([p['volume'] for p in res.data['results']], [1100])

    def test_filter_options(self):
        res = self.client.get('/api/shop/products/filters/')
        self.assertEqual(res.data['volumes'], [240, 660, 1100])
        self.assertEqual({m['value'] for m in res.data['materials']}, {'plastic', 'metal', 'galvanized'})
        self.assertEqual(Decimal(res.data['price']['min']), Decimal('3500'))

    def test_hidden_product_not_public(self):
        self.assertEqual(self.client.get(f'/api/shop/products/{self.hidden.id}/').status_code, 404)

    def test_anonymous_and_other_staff_cannot_write(self):
        payload = {'name_ru': 'X', 'volume': 10, 'material': 'plastic', 'price': '1'}
        self.assertEqual(self.client.post('/api/shop/products/', payload, format='json').status_code, 401)
        self.client.force_authenticate(self.content)
        self.assertEqual(self.client.post('/api/shop/products/', payload, format='json').status_code, 403)

    def test_manager_creates_product_with_image(self):
        self.client.force_authenticate(self.manager)
        payload = {'name_ru': 'Бак 120', 'volume': 120, 'material': 'plastic', 'price': '2500', 'image': PNG_DATA_URL}
        res = self.client.post('/api/shop/products/', payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['image'].startswith('http://testserver/media/shop/products/'))
        self.assertTrue(res.data['image'].endswith('.png'))

        # ссылка вместо data URL — фото не меняется
        product_id = res.data['id']
        res = self.client.patch(f'/api/shop/products/{product_id}/', {'image': res.data['image'], 'price': '2600'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(Product.objects.get(id=product_id).image.name.endswith('.png'))

    def test_manager_sees_hidden_with_all(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get('/api/shop/products/?all=1').data['count'], 4)
        self.assertEqual(self.client.get(f'/api/shop/products/{self.hidden.id}/').status_code, 200)

    def test_image_with_wrong_content_rejected(self):
        self.client.force_authenticate(self.manager)
        fake = 'data:image/png;base64,' + base64.b64encode(b'<script>alert(1)</script>').decode()
        res = self.client.post(
            '/api/shop/products/',
            {'name_ru': 'X', 'volume': 10, 'material': 'plastic', 'price': '1', 'image': fake},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        svg = 'data:image/svg+xml;base64,' + base64.b64encode(b'<svg/>').decode()
        res = self.client.post(
            '/api/shop/products/',
            {'name_ru': 'X', 'volume': 10, 'material': 'plastic', 'price': '1', 'image': svg},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    # ---------- заказы ----------
    def _order(self, **overrides):
        data = {
            'customer_name': 'Айбек',
            'phone': '+996 555 123 456',
            'delivery_method': 'pickup',
            'items': [{'product': str(self.p240.id), 'quantity': 2}, {'product': str(self.p1100.id), 'quantity': 1}],
        }
        data.update(overrides)
        return self.client.post('/api/shop/orders/', data, format='json')

    @mock.patch('shop.views.send_order_notification', return_value=True)
    def test_order_total_is_computed_on_server(self, notify):
        res = self._order(total='1')
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(id=res.data['number'])
        self.assertEqual(order.total, Decimal('32000'))
        self.assertEqual(order.items.count(), 2)
        self.assertTrue(order.telegram_notified)
        self.assertIn('https://t.me/tazalyk_shop?text=', res.data['telegram_url'])
        notify.assert_called_once()

    @mock.patch('shop.views.send_order_notification', return_value=False)
    def test_order_rejects_unavailable_and_hidden(self, _):
        self.assertEqual(self._order(items=[{'product': str(self.out.id), 'quantity': 1}]).status_code, 400)
        self.assertEqual(self._order(items=[{'product': str(self.hidden.id), 'quantity': 1}]).status_code, 400)
        self.assertEqual(self._order(items=[]).status_code, 400)
        self.assertEqual(self._order(items=[{'product': str(self.p240.id), 'quantity': 101}]).status_code, 400)

    @mock.patch('shop.views.send_order_notification', return_value=False)
    def test_order_validation(self, _):
        self.assertEqual(self._order(delivery_method='delivery').status_code, 400)  # нет адреса
        self.assertEqual(self._order(delivery_method='delivery', address='ул. Токтогула 1').status_code, 201)
        self.assertEqual(self._order(phone='позвоните мне').status_code, 400)
        self.assertEqual(self._order(website='http://spam').status_code, 400)  # ловушка для ботов

    @mock.patch('shop.views.send_order_notification', return_value=True)
    def test_buyer_gets_manager_links_with_order_text(self, _):
        res = self._order(contact_method='telegram')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['contact_method'], 'telegram')
        self.assertEqual(Order.objects.get(id=res.data['number']).contact_method, 'telegram')
        self.assertTrue(res.data['whatsapp_url'].startswith('https://wa.me/996700111222?text='))
        text = unquote(res.data['whatsapp_url'].split('?text=')[1])
        self.assertIn(f'№{res.data["number"]}', text)
        self.assertIn('32 000 сом', text)
        # личные данные покупателя не проходят через адрес ссылки
        self.assertNotIn('Айбек', text)
        self.assertNotIn('555', text)

    @override_settings(SHOP_TELEGRAM_USERNAME='', SHOP_WHATSAPP_PHONE='')
    @mock.patch('shop.views.send_order_notification', return_value=False)
    def test_order_works_without_manager_contacts(self, _):
        res = self._order()
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.data['whatsapp_url'])
        self.assertIsNone(res.data['telegram_url'])
        self.assertEqual(res.data['contact_method'], 'whatsapp')

    @mock.patch('shop.views.send_order_notification', return_value=False)
    def test_contact_and_phone_are_validated(self, _):
        self.assertEqual(self._order(contact_method='viber').status_code, 400)
        self.assertEqual(self._order(phone='123-45-67').status_code, 400)  # неполный номер
        self.assertEqual(self._order(phone='0555 123 456').status_code, 201)

    def test_phone_is_converted_to_international(self):
        for phone in ('+996 555 123 456', '0555 123 456', '555123456', '(0555) 12-34-56', '00996555123456'):
            self.assertEqual(international_phone(phone), '996555123456', phone)
        self.assertEqual(international_phone('+7 701 123 45 67'), '77011234567')

    @override_settings(TELEGRAM_BOT_TOKEN='token', TELEGRAM_ORDERS_CHAT_ID='1')
    def test_manager_notification_has_links_to_buyer(self):
        with mock.patch('shop.telegram.urllib.request.urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value.status = 200
            res = self._order(customer_name='<b>Айбек</b>', phone='0555 123 456', contact_method='telegram')
        self.assertEqual(res.status_code, 201, res.data)
        text = json.loads(urlopen.call_args.args[0].data)['text']
        self.assertIn('Удобнее: Telegram', text)
        self.assertIn('https://wa.me/996555123456?text=', text)
        self.assertIn('https://t.me/+996555123456', text)
        self.assertIn('&lt;b&gt;Айбек', text)
        self.assertTrue(Order.objects.get(id=res.data['number']).telegram_notified)

    @mock.patch('shop.views.send_order_notification', return_value=True)
    def test_manager_sees_buyer_links_in_admin(self, _):
        number = self._order(phone='0555 123 456').data['number']
        self.client.force_authenticate(self.manager)
        data = self.client.get(f'/api/shop/orders/{number}/').data
        self.assertEqual(data['contact_label'], 'WhatsApp')
        self.assertTrue(data['customer_whatsapp_url'].startswith('https://wa.me/996555123456?text='))
        self.assertEqual(data['customer_telegram_url'], 'https://t.me/+996555123456')

    def test_orders_are_private(self):
        self.assertEqual(self.client.get('/api/shop/orders/').status_code, 401)
        self.client.force_authenticate(self.content)
        self.assertEqual(self.client.get('/api/shop/orders/').status_code, 403)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get('/api/shop/orders/').status_code, 200)

    @mock.patch('shop.views.send_order_notification', return_value=False)
    def test_manager_changes_only_status(self, _):
        number = self._order().data['number']
        self.client.force_authenticate(self.manager)
        res = self.client.patch(f'/api/shop/orders/{number}/', {'status': 'paid', 'total': '1'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        order = Order.objects.get(id=number)
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.total, Decimal('32000'))
        # удалять заказы может только администратор
        self.assertEqual(self.client.delete(f'/api/shop/orders/{number}/').status_code, 403)

    @mock.patch('shop.views.send_order_notification', return_value=False)
    def test_order_rate_limit(self, _):
        codes = [self._order().status_code for _ in range(11)]
        self.assertEqual(codes[:10], [201] * 10)
        self.assertEqual(codes[10], 429)

    def test_me_endpoint(self):
        self.assertEqual(self.client.get('/api/me/').status_code, 401)
        self.client.force_authenticate(self.manager)
        res = self.client.get('/api/me/')
        self.assertEqual(res.data['groups'], ['shop_managers'])
        self.assertFalse(res.data['is_superuser'])
