import os
import tempfile
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

def read_env():
    env_vars = {}
    env_path = os.path.join(BASE_DIR, '.env')
    
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    env_vars.update({key: value for key, value in os.environ.items() if value})
    return env_vars

ENV = read_env()

SECRET_KEY = ENV.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('DJANGO_SECRET_KEY не задан в backend/.env')
DEBUG = ENV.get('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'mptazalyk.kg',
    'admin.mptazalyk.kg',
    'api.mptazalyk.kg',
    '195.38.166.151',
    'backend',
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'api',
    'shop',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tazalyk.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tazalyk.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': ENV.get('DB_NAME', 'tazalyk'),
        'USER': ENV.get('DB_USER', 'postgres'),
        'PASSWORD': ENV.get('DB_PASSWORD', ''),
        'HOST': ENV.get('DB_HOST', 'localhost'),
        'PORT': ENV.get('DB_PORT', '5432'),
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(tempfile.gettempdir(), 'tazalyk-cache'),
        'OPTIONS': {'MAX_ENTRIES': 10000},
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Bishkek'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'staticfiles')]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in ENV.get(
        'CORS_ALLOWED_ORIGINS',
        'https://mptazalyk.kg,https://www.mptazalyk.kg,https://admin.mptazalyk.kg',
    ).split(',')
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r'^/(api|media)/.*$'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.CookieJWTAuthentication',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'api.parsers.SafeJSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'] + (
        ['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []
    ),
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '600/min',
        'shop_orders': '10/hour',
        'vacancy_applications': '10/hour',
        'login': '5/min',
        'token_refresh': '30/min',
        'search': '120/min',
    },
    'NUM_PROXIES': int(ENV.get('DRF_NUM_PROXIES', '0')),
}

TELEGRAM_BOT_TOKEN = ENV.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ORDERS_CHAT_ID = ENV.get('TELEGRAM_ORDERS_CHAT_ID', '')
TELEGRAM_ALERTS_CHAT_ID = ENV.get('TELEGRAM_ALERTS_CHAT_ID', '')
SHOP_TELEGRAM_USERNAME = ENV.get('SHOP_TELEGRAM_USERNAME', '')
SHOP_WHATSAPP_PHONE = ENV.get('SHOP_WHATSAPP_PHONE', '')
PUBLIC_MEDIA_BASE_URL = ENV.get('PUBLIC_MEDIA_BASE_URL', '')

APPLICATIONS_DAILY_BYTES = int(ENV.get('APPLICATIONS_DAILY_BYTES', str(300 * 1024 * 1024)))

COMPLAINTS_INTAKE_TOKEN = ENV.get('COMPLAINTS_INTAKE_TOKEN', '')
COMPLAINTS_DAILY_BYTES = int(ENV.get('COMPLAINTS_DAILY_BYTES', str(300 * 1024 * 1024)))

ADMIN_ORIGINS = [
    origin.strip()
    for origin in ENV.get('ADMIN_ORIGINS', 'https://admin.mptazalyk.kg').split(',')
    if origin.strip()
]
AUTH_COOKIE_SECURE = ENV.get('AUTH_COOKIE_SECURE', 'True') == 'True'

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'UPDATE_LAST_LOGIN': True,
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'CHECK_REVOKE_TOKEN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

if ENV.get('DJANGO_HTTPS', 'False') == 'True':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r'^api/health/?$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = ['https://api.mptazalyk.kg', 'https://admin.mptazalyk.kg']
    SECURE_HSTS_SECONDS = int(ENV.get('DJANGO_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}

APPEND_SLASH = False