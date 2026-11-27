import re
from urllib.parse import quote

from django.conf import settings

MAX_MESSAGE_ITEMS = 5
PHONE_RE = re.compile(r'^\+?[0-9\s\-()]{7,20}$')
MIN_PHONE_DIGITS = 11
MAX_PHONE_DIGITS = 15


def format_money(value):
    return f'{value:,.0f}'.replace(',', ' ')


def international_phone(phone):
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('00'):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith('0'):
        digits = digits[1:]
    if len(digits) == 9:
        digits = f'996{digits}'
    return digits


def is_valid_phone(phone):
    return MIN_PHONE_DIGITS <= len(international_phone(phone)) <= MAX_PHONE_DIGITS


def _order_message(order):
    items = list(order.items.all())
    lines = [f'Здравствуйте! Мой заказ №{order.id} на сайте МП «Тазалык»:']
    lines += [f'• {item.product_name} ({item.volume} л) × {item.quantity}' for item in items[:MAX_MESSAGE_ITEMS]]
    if len(items) > MAX_MESSAGE_ITEMS:
        lines.append(f'…и ещё позиций: {len(items) - MAX_MESSAGE_ITEMS}')
    lines.append(f'Сумма: {format_money(order.total)} сом')
    lines.append(f'Получение: {order.get_delivery_method_display().lower()}')
    return '\n'.join(lines)


def manager_links(order):
    text = quote(_order_message(order))
    whatsapp = international_phone(settings.SHOP_WHATSAPP_PHONE)
    username = settings.SHOP_TELEGRAM_USERNAME.lstrip('@')
    return {
        'whatsapp_url': f'https://wa.me/{whatsapp}?text={text}' if whatsapp else None,
        'telegram_url': f'https://t.me/{username}?text={text}' if username else None,
    }


def customer_links(order):
    phone = international_phone(order.phone)
    text = quote(f'Здравствуйте, {order.customer_name}! Это МП «Тазалык», ваш заказ №{order.id}.')
    username = order.telegram.lstrip('@')
    return {
        'whatsapp_url': f'https://wa.me/{phone}?text={text}',
        'telegram_url': f'https://t.me/{username}' if username else f'https://t.me/+{phone}',
    }
