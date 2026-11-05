import html
import json
import logging
import urllib.request

from django.conf import settings

from .contacts import customer_links, format_money

logger = logging.getLogger(__name__)


def send_order_notification(order):
    """Отправляет новый заказ в Telegram-чат менеджеров. Ошибка не мешает оформлению заказа."""
    chat_id = getattr(settings, 'TELEGRAM_ORDERS_CHAT_ID', '')
    if not getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or not chat_id:
        logger.warning('Telegram для заказов не настроен: заказ №%s не отправлен', order.id)
        return False

    esc = html.escape
    lines = [
        f'🛒 <b>Новый заказ №{order.id}</b>',
        '',
        f'👤 {esc(order.customer_name)}',
        f'📞 {esc(order.phone)}',
    ]
    links = customer_links(order)
    lines.append(f'💬 Удобнее: {esc(order.get_contact_method_display())}')
    lines.append(
        f'<a href="{esc(links["whatsapp_url"])}">Написать в WhatsApp</a>'
        f' · <a href="{esc(links["telegram_url"])}">Написать в Telegram</a>'
    )
    lines.append(f'🚚 {esc(order.get_delivery_method_display())}' + (f': {esc(order.address)}' if order.address else ''))
    lines.append('')
    for item in order.items.all():
        lines.append(f'• {esc(item.product_name)} ({item.volume} л) × {item.quantity} = {format_money(item.subtotal)} сом')
    lines.append('')
    lines.append(f'💰 <b>Итого: {format_money(order.total)} сом</b>')
    if order.comment:
        lines.append(f'💬 {esc(order.comment)}')

    return _send_message(chat_id, '\n'.join(lines), parse_mode='HTML')


def send_security_alert(text):
    """Оповещение о подозрительной активности в отдельный чат: текст простой, без разметки"""
    chat_id = getattr(settings, 'TELEGRAM_ALERTS_CHAT_ID', '')
    if not getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or not chat_id:
        logger.warning('Telegram для оповещений не настроен: %s', text)
        return False
    return _send_message(chat_id, f'МП «Тазалык»: {text}')


def _send_message(chat_id, text, parse_mode=None):
    message = {'chat_id': chat_id, 'text': text, 'disable_web_page_preview': True}
    if parse_mode:
        message['parse_mode'] = parse_mode
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage',
        data=json.dumps(message).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception as exc:
        # в тексте ошибки может оказаться адрес с токеном бота — пишем только тип ошибки
        logger.error('Не удалось отправить сообщение в Telegram: %s', type(exc).__name__)
        return False
