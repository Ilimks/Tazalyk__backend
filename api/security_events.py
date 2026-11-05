"""Журнал входов и оповещения о подборе паролей.

Сигнал user_login_failed срабатывает и для входа в админку через API, и для /admin/.
"""
import logging

from django.contrib.auth.signals import user_login_failed
from django.core.cache import cache
from django.dispatch import receiver
from rest_framework.throttling import BaseThrottle

from shop.telegram import send_security_alert

logger = logging.getLogger('security')

# столько неудачных входов за окно считаем подбором пароля
ALERT_AFTER = 5
WINDOW_SECONDS = 10 * 60
# по одному адресу или логину — не больше одного сообщения в час, чтобы не завалить чат
ALERT_COOLDOWN_SECONDS = 60 * 60


def client_ip(request):
    # адрес определяется так же, как у лимитов: X-Forwarded-For учитывается только за nginx
    return BaseThrottle().get_ident(request) if request is not None else 'unknown'


def _count_failure(key, description):
    count = cache.get(key, 0) + 1
    cache.set(key, count, WINDOW_SECONDS)
    if count >= ALERT_AFTER and cache.add(f'alerted:{key}', 1, ALERT_COOLDOWN_SECONDS):
        send_security_alert(f'Возможен подбор пароля: {count} неудачных входов за 10 минут. {description}')


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    ip = client_ip(request)
    username = str(credentials.get('username', ''))[:64]
    logger.warning('Неудачный вход: user=%r ip=%s', username, ip)
    _count_failure(f'failed_logins:ip:{ip}', f'Адрес: {ip}')
    _count_failure(f'failed_logins:user:{username}', f'Логин: {username}')


def log_login_success(request, username):
    logger.info('Успешный вход: user=%r ip=%s', str(username)[:64], client_ip(request))


def log_login_throttled(request):
    logger.warning('Вход заблокирован лимитом: ip=%s', client_ip(request))
