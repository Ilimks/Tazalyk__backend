import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# ========== ТОВАРЫ ==========
class Product(models.Model):
    MATERIAL_CHOICES = [
        ('plastic', 'Пластик'),
        ('metal', 'Металл'),
        ('galvanized', 'Оцинкованный металл'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_ru = models.CharField(max_length=200, verbose_name='Название (Русский)')
    name_ky = models.CharField(max_length=200, blank=True, verbose_name='Название (Кыргызча)')
    description_ru = models.TextField(blank=True, verbose_name='Описание (Русский)')
    description_ky = models.TextField(blank=True, verbose_name='Описание (Кыргызча)')
    volume = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100000)],
        verbose_name='Объём, л',
    )
    material = models.CharField(max_length=20, choices=MATERIAL_CHOICES, verbose_name='Материал')
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Цена, сом',
    )
    # фото хранится файлом в MEDIA_ROOT, в базе — только путь
    image = models.FileField(upload_to='shop/products/', blank=True, verbose_name='Фото')
    in_stock = models.BooleanField(default=True, verbose_name='В наличии')
    is_featured = models.BooleanField(default=False, verbose_name='Показывать на главной')
    is_active = models.BooleanField(default=True, verbose_name='Опубликован')
    sort_order = models.IntegerField(default=0, verbose_name='Порядок')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        ordering = ['sort_order', '-created_at']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        indexes = [
            models.Index(fields=['is_active', 'volume'], name='shop_product_active_volume'),
            models.Index(fields=['price'], name='shop_product_price'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(price__gte=0), name='shop_product_price_gte_0'),
        ]

    def __str__(self):
        return f'{self.name_ru} ({self.volume} л)'


# ========== ЗАКАЗЫ ==========
class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('awaiting_payment', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('completed', 'Выполнен'),
        ('cancelled', 'Отменён'),
    ]
    DELIVERY_CHOICES = [
        ('pickup', 'Самовывоз'),
        ('delivery', 'Доставка'),
    ]
    CONTACT_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
    ]

    # номер заказа (1, 2, 3…) — его покупатель называет менеджеру в чате
    id = models.BigAutoField(primary_key=True)
    customer_name = models.CharField(max_length=150, verbose_name='Имя покупателя')
    phone = models.CharField(max_length=30, verbose_name='Телефон')
    telegram = models.CharField(max_length=64, blank=True, verbose_name='Telegram')
    contact_method = models.CharField(
        max_length=20, choices=CONTACT_CHOICES, default='whatsapp', verbose_name='Способ связи',
    )
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, verbose_name='Получение')
    address = models.CharField(max_length=300, blank=True, verbose_name='Адрес доставки')
    comment = models.TextField(blank=True, verbose_name='Комментарий покупателя')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    total = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Сумма, сом')
    manager_note = models.TextField(blank=True, verbose_name='Заметка менеджера')
    telegram_notified = models.BooleanField(default=False, verbose_name='Отправлен в Telegram')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        indexes = [
            models.Index(fields=['status', '-created_at'], name='shop_order_status_created'),
        ]

    def __str__(self):
        return f'Заказ №{self.id}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    # товар могут удалить из каталога — название, объём и цена копируются в позицию заказа
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Товар')
    product_name = models.CharField(max_length=200, verbose_name='Название товара')
    volume = models.PositiveIntegerField(verbose_name='Объём, л')
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Цена, сом')
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Количество',
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'

    @property
    def subtotal(self):
        return self.price * self.quantity
