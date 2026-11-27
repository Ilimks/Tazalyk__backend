from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication

ACCESS_COOKIE = 'tazalyk_access'
REFRESH_COOKIE = 'tazalyk_refresh'
ACCESS_COOKIE_PATH = '/api/'
REFRESH_COOKIE_PATH = '/api/token/'


def _is_admin_origin(request):
    return request.headers.get('Origin') in settings.ADMIN_ORIGINS


def require_admin_origin(request):
    if not _is_admin_origin(request):
        raise PermissionDenied('Запрос не из панели управления.')


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if raw_token is None:
            return super().authenticate(request)

        if request.method in SAFE_METHODS:
            if 'Origin' in request.headers and not _is_admin_origin(request):
                return None
        else:
            require_admin_origin(request)

        validated_token = self.get_validated_token(raw_token.encode())
        return self.get_user(validated_token), validated_token


def set_auth_cookies(response, access, refresh):
    max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    common = {'httponly': True, 'secure': settings.AUTH_COOKIE_SECURE, 'samesite': 'Strict', 'max_age': max_age}
    response.set_cookie(ACCESS_COOKIE, access, path=ACCESS_COOKIE_PATH, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, path=REFRESH_COOKIE_PATH, **common)


def delete_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_COOKIE_PATH, samesite='Strict')
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite='Strict')
