"""Вход в админку: токены лежат в cookie с HttpOnly, скрипт на странице не может их прочитать.

Браузер сам прикладывает cookie к запросам, поэтому важно понимать, откуда запрос. Запрос с другого
сайта вошедшим не считается. Этого достаточно вместе с SameSite=Strict: заголовок Origin браузер
ставит сам, и страница не может его подделать.
"""
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication

ACCESS_COOKIE = 'tazalyk_access'
REFRESH_COOKIE = 'tazalyk_refresh'
ACCESS_COOKIE_PATH = '/api/'
# длинный токен браузер отправляет только на адреса входа, выхода и обновления
REFRESH_COOKIE_PATH = '/api/token/'


def _is_admin_origin(request):
    return request.headers.get('Origin') in settings.ADMIN_ORIGINS


def require_admin_origin(request):
    """Для запросов, которые меняют данные: браузер всегда указывает Origin у таких запросов"""
    if not _is_admin_origin(request):
        raise PermissionDenied('Запрос не из панели управления.')


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if raw_token is None:
            # заголовок Authorization: панель, открытая до обновления сервера, доживает свою сессию
            return super().authenticate(request)

        if request.method in SAFE_METHODS:
            # чтение с чужого сайта: остаётся посетителем, публичные данные ему и так доступны
            if 'Origin' in request.headers and not _is_admin_origin(request):
                return None
        else:
            require_admin_origin(request)

        validated_token = self.get_validated_token(raw_token.encode())
        return self.get_user(validated_token), validated_token


def set_auth_cookies(response, access, refresh):
    # Cookie живёт дольше короткого токена: истёкший токен даёт ответ 401, и админка обновляет его.
    # Без cookie запрос выглядел бы как обычный посетитель и получал бы только публичные данные
    max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    common = {'httponly': True, 'secure': settings.AUTH_COOKIE_SECURE, 'samesite': 'Strict', 'max_age': max_age}
    response.set_cookie(ACCESS_COOKIE, access, path=ACCESS_COOKIE_PATH, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, path=REFRESH_COOKIE_PATH, **common)


def delete_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_COOKIE_PATH, samesite='Strict')
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite='Strict')
