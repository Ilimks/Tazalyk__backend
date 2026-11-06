import os
import tempfile
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

def read_env():
    """Настройки из .env и окружения. На сервере они приходят из env_file в docker-compose,
    поэтому окружение важнее файла. Пустые переменные пропускаем: compose подставляет пустую
    строку, если значения нет, и это не должно затирать настройку из файла."""
    env_vars = {}
    env_path = os.path.join(BASE_DIR, '.env')
    
    if os.path.exists(env_path):
        # utf-8-sig: Блокнот сохраняет .env с BOM, и без этого первая строка
        # (DJANGO_SECRET_KEY) не читалась — Django брал небезопасный ключ по умолчанию
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

# ========== БЕЗОПАСНОСТЬ ==========
# Без ключа сервер не запускается: раньше подставлялся публичный ключ из репозитория,
# и любой мог подписать себе токен администратора
SECRET_KEY = ENV.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('DJANGO_SECRET_KEY не задан в backend/.env')
# по умолчанию отладка выключена: если .env потеряется, ошибки не покажут код и настройки
DEBUG = ENV.get('DJANGO_DEBUG', 'False') == 'True'
# ALLOWED_HOSTS = ENV.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
# ALLOWED_HOSTS = [
#     'localhost', 
#     '127.0.0.1', 
#     '172.16.11.131', 
#     '172.16.11.53',
#     'ваш-домен.kg', 
#     'www.ваш-домен.kg'
# ]
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'mptazalyk.kg',
    'admin.mptazalyk.kg',
    'api.mptazalyk.kg',
    '195.38.166.151',  # Добавить когда получите
]


# ========== ПРИЛОЖЕНИЯ ==========
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
        'NAME': ENV.get('DB_NAME', 'tazalyk'),        # ← ENV.get, а не os.getenv
        'USER': ENV.get('DB_USER', 'postgres'),
        'PASSWORD': ENV.get('DB_PASSWORD', ''),
        'HOST': ENV.get('DB_HOST', 'localhost'),
        'PORT': ENV.get('DB_PORT', '5432'),
    }
}

# ========== КЭШ ==========
# Здесь живут счётчики лимитов (вход, заказы). Кэш в памяти у каждого процесса gunicorn свой,
# и лимит умножался бы на число процессов, поэтому кэш лежит в файлах
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(tempfile.gettempdir(), 'tazalyk-cache'),
        'OPTIONS': {'MAX_ENTRIES': 10000},
    }
}

# ========== ВАЛИДАЦИЯ ПАРОЛЕЙ ==========
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    # старые пароли продолжают работать и пересчитываются в Argon2 при следующем входе
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========== ЛОКАЛИЗАЦИЯ ==========
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Bishkek'
USE_I18N = True
USE_TZ = True

# ========== СТАТИКА ==========
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'staticfiles')]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========== CORS ==========
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:5173",
#     "http://127.0.0.1:5173", 
#     "http://localhost:3000",
#     "http://localhost",
#     "http://127.0.0.1",
#     "http://localhost:80",
#     "http://localhost:8000",
#     "http://172.16.11.131:8000",
#     "http://172.16.11.53:8000",   # ← ДОБАВИТЬ НОВЫЙ IP
#     "http://172.16.11.53",        # ← ДЛЯ АДМИНКИ
# ]

# Запросы из браузера принимаются только с сайта и админки. Список можно переопределить
# в .env: CORS_ALLOWED_ORIGINS=https://mptazalyk.kg,https://admin.mptazalyk.kg
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in ENV.get(
        'CORS_ALLOWED_ORIGINS',
        # локальные адреса задаются только в .env разработчика (см. .env.example)
        'https://mptazalyk.kg,https://www.mptazalyk.kg,https://admin.mptazalyk.kg',
    ).split(',')
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = False
# вход по JWT в заголовке Authorization — cookie браузеру передавать не нужно
# cookie входа принимаются только из панели управления: см. api/authentication.py
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r'^/(api|media)/.*$'

# ========== REST FRAMEWORK ==========
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
    # HTML-страницы «просматриваемого» API только при отладке: на сервере они раскрывают структуру API
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'] + (
        ['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []
    ),
    # Общий лимит для посетителей: публичные списки тяжёлые, а без входа их мог запрашивать кто угодно.
    # Запросы сайта при серверной отрисовке идут с одного адреса, поэтому запас большой
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '600/min',
        # оформление заказов в магазине с одного адреса
        'shop_orders': '10/hour',
        # резюме с сайта: посетитель может откликнуться на несколько вакансий, бот — нет
        'vacancy_applications': '10/hour',
        # попытки входа в админку с одного адреса — защита от подбора пароля
        'login': '5/min',
        'token_refresh': '30/min',
        # подсказки в строке поиска идут на каждое слово
        'search': '120/min',
    },
    # Сколько прокси стоит перед Django. 0 — адрес клиента берётся из соединения (локально);
    # за nginx на сервере нужно DRF_NUM_PROXIES=1, иначе лимиты считались бы по адресу nginx,
    # а при None адрес можно подделать заголовком X-Forwarded-For
    'NUM_PROXIES': int(ENV.get('DRF_NUM_PROXIES', '0')),
}

# ========== МАГАЗИН ==========
# Бот присылает новые заказы в чат менеджеров. Токен выдаёт @BotFather, chat_id — id чата/группы.
TELEGRAM_BOT_TOKEN = ENV.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ORDERS_CHAT_ID = ENV.get('TELEGRAM_ORDERS_CHAT_ID', '')
# Чат для оповещений о подборе паролей: в него не должны смотреть менеджеры продаж
TELEGRAM_ALERTS_CHAT_ID = ENV.get('TELEGRAM_ALERTS_CHAT_ID', '')
# Контакты менеджера: сюда покупатель пишет после оформления заказа.
# Telegram — имя без @, WhatsApp — номер с кодом страны. Пустое значение скрывает кнопку
SHOP_TELEGRAM_USERNAME = ENV.get('SHOP_TELEGRAM_USERNAME', '')
SHOP_WHATSAPP_PHONE = ENV.get('SHOP_WHATSAPP_PHONE', '')
# Адрес, с которого отдаются фото товаров, например https://api.mptazalyk.kg.
# Пусто — адрес берётся из запроса (локально http://localhost:8000).
PUBLIC_MEDIA_BASE_URL = ENV.get('PUBLIC_MEDIA_BASE_URL', '')

# ========== ОТКЛИКИ НА ВАКАНСИИ ==========
# Сколько резюме в байтах можно принять за сутки со всех адресов вместе
APPLICATIONS_DAILY_BYTES = int(ENV.get('APPLICATIONS_DAILY_BYTES', str(300 * 1024 * 1024)))

# ========== JWT ==========
# Откуда принимаются cookie входа. Локально: ADMIN_ORIGINS=http://localhost
ADMIN_ORIGINS = [
    origin.strip()
    for origin in ENV.get('ADMIN_ORIGINS', 'https://admin.mptazalyk.kg').split(',')
    if origin.strip()
]
# без https cookie с Secure браузер не отправит: локально AUTH_COOKIE_SECURE=False
AUTH_COOKIE_SECURE = ENV.get('AUTH_COOKIE_SECURE', 'True') == 'True'

SIMPLE_JWT = {
    # короткий токен доступа: украденный токен быстрее перестаёт работать (админка обновляет его сама)
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'UPDATE_LAST_LOGIN': True,
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    # после смены пароля все выданные токены перестают действовать
    'CHECK_REVOKE_TOKEN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ========== БЕЗОПАСНОСТЬ ==========
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

# На сервере за HTTPS-прокси (nginx) включить DJANGO_HTTPS=True в .env.
# Локально по http эти настройки не включаются, иначе всё перенаправлялось бы на https
if ENV.get('DJANGO_HTTPS', 'False') == 'True':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r'^api/health/?$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = ['https://api.mptazalyk.kg', 'https://admin.mptazalyk.kg']
    # сначала час; когда всё проверено — 31536000 (год)
    SECURE_HSTS_SECONDS = int(ENV.get('DJANGO_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# ========== ЛОГИ ==========
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}

APPEND_SLASH = False