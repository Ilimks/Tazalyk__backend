"""Связь покупателя и менеджера: ссылки в WhatsApp и Telegram с готовым текстом о заказе."""
import re
from urllib.parse import quote

from django.conf import settings

# ссылка с текстом не должна быть слишком длинной: мессенджеры обрезают такие адреса
MAX_MESSAGE_ITEMS = 5
MIN_PHONE_DIGITS = 11
MAX_PHONE_DIGITS = 15


def format_money(value):
    return f'{value:,.0f}'.replace(',', ' ')


def international_phone(phone):
    """Номер цифрами с кодом страны: в Кыргызстане часто пишут 0555… или просто 555…"""
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
    """Текст от покупателя. Только сам заказ: имя и телефон менеджер видит в админке,
    а личным данным незачем проходить через адрес ссылки"""
    items = list(order.items.all())
    lines = [f'Здравствуйте! Мой заказ №{order.id} на сайте МП «Тазалык»:']
    lines += [f'• {item.product_name} ({item.volume} л) × {item.quantity}' for item in items[:MAX_MESSAGE_ITEMS]]
    if len(items) > MAX_MESSAGE_ITEMS:
        lines.append(f'…и ещё позиций: {len(items) - MAX_MESSAGE_ITEMS}')
    lines.append(f'Сумма: {format_money(order.total)} сом')
    lines.append(f'Получение: {order.get_delivery_method_display().lower()}')
    return '\n'.join(lines)


def manager_links(order):
    """Ссылки для покупателя: чат с менеджером. None — контакт менеджера не настроен"""
    text = quote(_order_message(order))
    whatsapp = international_phone(settings.SHOP_WHATSAPP_PHONE)
    username = settings.SHOP_TELEGRAM_USERNAME.lstrip('@')
    return {
        'whatsapp_url': f'https://wa.me/{whatsapp}?text={text}' if whatsapp else None,
        'telegram_url': f'https://t.me/{username}?text={text}' if username else None,
    }


def customer_links(order):
    """Ссылки для менеджера: написать покупателю, даже если тот сам не вышел на связь"""
    phone = international_phone(order.phone)
    text = quote(f'Здравствуйте, {order.customer_name}! Это МП «Тазалык», ваш заказ №{order.id}.')
    username = order.telegram.lstrip('@')
    return {
        'whatsapp_url': f'https://wa.me/{phone}?text={text}',
        # Telegram открывает чат по номеру; готовый текст в такой ссылке не поддерживается
        'telegram_url': f'https://t.me/{username}' if username else f'https://t.me/+{phone}',
    }
