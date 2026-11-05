import base64
import binascii
import re
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers

from .contacts import customer_links, is_valid_phone
from .models import Order, OrderItem, Product

# ========== ФОТО ТОВАРА ==========
MAX_IMAGE_BYTES = 5 * 1024 * 1024
DATA_URL_RE = re.compile(r'^data:(image/(?:jpeg|png|webp));base64,(.+)$', re.S)
# расширение и «подпись» начала файла для каждого разрешённого типа
IMAGE_SIGNATURES = {
    'image/jpeg': ('jpg', lambda b: b[:3] == b'\xff\xd8\xff'),
    'image/png': ('png', lambda b: b[:8] == b'\x89PNG\r\n\x1a\n'),
    'image/webp': ('webp', lambda b: b[:4] == b'RIFF' and b[8:12] == b'WEBP'),
}


class DataURLImageField(serializers.FileField):
    """Принимает фото как data URL (так его отдаёт админка), сохраняет обычным файлом.

    Строка-ссылка вместо data URL значит «фото не менялось», пустая строка — «удалить фото».
    """

    def to_internal_value(self, data):
        if data in ('', None):
            return ''
        if not isinstance(data, str):
            raise serializers.ValidationError('Ожидается изображение в формате data URL.')
        if not data.startswith('data:'):
            raise serializers.SkipField()

        match = DATA_URL_RE.match(data)
        if not match:
            raise serializers.ValidationError('Допустимы только JPEG, PNG и WebP.')
        mime, payload = match.groups()
        # base64 длиннее исходного файла на треть — отсекаем огромные строки до декодирования
        if len(payload) > MAX_IMAGE_BYTES * 4 // 3 + 4:
            raise serializers.ValidationError('Фото больше 5 МБ.')
        try:
            raw = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError('Повреждённые данные изображения.')

        ext, signature_ok = IMAGE_SIGNATURES[mime]
        if not signature_ok(raw):
            raise serializers.ValidationError('Содержимое файла не совпадает с его типом.')
        return ContentFile(raw, name=f'{uuid.uuid4().hex}.{ext}')

    def to_representation(self, value):
        if not value:
            return None
        url = value.url
        # на сервере за прокси адрес задаётся явно, чтобы не получить http:// на https-сайте
        base = getattr(settings, 'PUBLIC_MEDIA_BASE_URL', '')
        if base:
            return f'{base.rstrip("/")}{url}'
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class ProductSerializer(serializers.ModelSerializer):
    image = DataURLImageField(required=False, allow_null=True)
    material_label = serializers.CharField(source='get_material_display', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name_ru', 'name_ky',
            'description_ru', 'description_ky',
            'volume', 'material', 'material_label', 'price',
            'image', 'in_stock', 'is_featured', 'is_active', 'sort_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# ========== ЗАКАЗЫ ==========
PHONE_RE = re.compile(r'^\+?[0-9\s\-()]{7,20}$')
TELEGRAM_RE = re.compile(r'^@?[A-Za-z0-9_]{5,32}$')
MAX_ORDER_LINES = 20


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class OrderCreateSerializer(serializers.Serializer):
    """Оформление заказа с сайта. Цены и сумма считаются здесь, а не берутся у браузера."""

    customer_name = serializers.CharField(min_length=2, max_length=150, trim_whitespace=True)
    phone = serializers.CharField(max_length=30, trim_whitespace=True)
    telegram = serializers.CharField(max_length=64, required=False, allow_blank=True, trim_whitespace=True)
    contact_method = serializers.ChoiceField(choices=Order.CONTACT_CHOICES, default='whatsapp')
    delivery_method = serializers.ChoiceField(choices=Order.DELIVERY_CHOICES)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True, trim_whitespace=True)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, trim_whitespace=True)
    items = OrderItemInputSerializer(many=True)
    # ловушка для ботов: поле скрыто на сайте, человек его не заполняет
    website = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        # по этому номеру менеджер пишет в мессенджер, поэтому нужен полный номер
        if not PHONE_RE.match(value) or not is_valid_phone(value):
            raise serializers.ValidationError('Укажите номер телефона, например +996 555 123 456.')
        return value

    def validate_telegram(self, value):
        if value and not TELEGRAM_RE.match(value):
            raise serializers.ValidationError('Имя в Telegram — латиница, цифры и «_», от 5 символов.')
        return value.lstrip('@')

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('Корзина пуста.')
        if len(items) > MAX_ORDER_LINES:
            raise serializers.ValidationError(f'Не больше {MAX_ORDER_LINES} разных товаров в заказе.')

        # один и тот же товар, добавленный дважды, складываем в одну позицию
        quantities = {}
        for item in items:
            quantities[item['product']] = quantities.get(item['product'], 0) + item['quantity']

        products = Product.objects.in_bulk(list(quantities.keys()))
        lines = []
        for product_id, quantity in quantities.items():
            product = products.get(product_id)
            if not product or not product.is_active:
                raise serializers.ValidationError('Один из товаров больше не продаётся. Обновите корзину.')
            if not product.in_stock:
                raise serializers.ValidationError(f'«{product.name_ru}» сейчас нет в наличии.')
            if quantity > 100:
                raise serializers.ValidationError('Не больше 100 штук одного товара.')
            lines.append((product, quantity))
        return lines

    def validate(self, attrs):
        if attrs.get('website'):
            raise serializers.ValidationError('Не удалось оформить заказ.')
        if attrs['delivery_method'] == 'delivery' and not attrs.get('address'):
            raise serializers.ValidationError({'address': 'Укажите адрес доставки.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop('items')
        validated_data.pop('website', None)
        if validated_data['delivery_method'] == 'pickup':
            validated_data['address'] = ''

        total = sum((product.price * quantity for product, quantity in lines), start=0)
        order = Order.objects.create(total=total, **validated_data)
        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=product,
                product_name=product.name_ru,
                volume=product.volume,
                price=product.price,
                quantity=quantity,
            )
            for product, quantity in lines
        ])
        return order


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'volume', 'price', 'quantity', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    """Заказ для админки: менять можно только статус и заметку менеджера."""

    items = OrderItemSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    delivery_label = serializers.CharField(source='get_delivery_method_display', read_only=True)
    contact_label = serializers.CharField(source='get_contact_method_display', read_only=True)
    customer_whatsapp_url = serializers.SerializerMethodField()
    customer_telegram_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'customer_name', 'phone', 'telegram',
            'contact_method', 'contact_label', 'customer_whatsapp_url', 'customer_telegram_url',
            'delivery_method', 'delivery_label', 'address', 'comment',
            'status', 'status_label', 'total', 'manager_note', 'telegram_notified',
            'items', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'customer_name', 'phone', 'telegram', 'contact_method', 'delivery_method', 'address', 'comment',
            'total', 'telegram_notified', 'created_at', 'updated_at',
        ]

    def get_customer_whatsapp_url(self, order):
        return customer_links(order)['whatsapp_url']

    def get_customer_telegram_url(self, order):
        return customer_links(order)['telegram_url']
