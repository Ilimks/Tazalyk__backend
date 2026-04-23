#!/usr/bin/env python
"""Скрипт проверки безопасности Django проекта
Запуск: python check_security.py
"""

import os
import sys
import re

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

# Настраиваем Django окружение
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tazalyk.settings')

try:
    import django
    django.setup()
except ImportError as e:
    print(f"❌ Ошибка импорта Django: {e}")
    print("Убедитесь, что виртуальное окружение активировано и Django установлен")
    sys.exit(1)

from django.conf import settings
from django.core.management import call_command
from django.contrib.auth import get_user_model

User = get_user_model()

def check_security():
    print("🔒 ПРОВЕРКА БЕЗОПАСНОСТИ ПРОЕКТА")
    print("="*60)
    
    issues = []
    warnings = []
    good = []
    
    # 1. Проверка SECRET_KEY
    print("\n1. Проверка SECRET_KEY...")
    if not settings.SECRET_KEY:
        issues.append("❌ SECRET_KEY не установлен!")
    elif settings.SECRET_KEY == 'django-insecure-your-secret-key-here-change-this':
        issues.append("❌ Используется НЕБЕЗОПАСНЫЙ SECRET_KEY по умолчанию!")
    elif len(settings.SECRET_KEY) < 50:
        warnings.append("⚠️ SECRET_KEY слишком короткий (< 50 символов)")
    else:
        good.append("✅ SECRET_KEY настроен корректно")
    
    # 2. Проверка DEBUG
    print("2. Проверка DEBUG режима...")
    if settings.DEBUG:
        issues.append("❌ DEBUG=True - НИКОГДА не используйте в production!")
    else:
        good.append("✅ DEBUG=False - безопасно для production")
    
    # 3. Проверка ALLOWED_HOSTS
    print("3. Проверка ALLOWED_HOSTS...")
    if not settings.ALLOWED_HOSTS:
        issues.append("❌ ALLOWED_HOSTS пуст!")
    elif '*' in settings.ALLOWED_HOSTS:
        if settings.DEBUG:
            warnings.append("⚠️ ALLOWED_HOSTS содержит '*' - допустимо только для разработки")
        else:
            issues.append("❌ ALLOWED_HOSTS содержит '*' в production режиме - ОПАСНО!")
    else:
        good.append(f"✅ ALLOWED_HOSTS настроен: {', '.join(settings.ALLOWED_HOSTS)}")
    
    # 4. Проверка HTTPS настроек
    print("4. Проверка HTTPS настроек...")
    if not settings.DEBUG:
        if not settings.SECURE_SSL_REDIRECT:
            issues.append("❌ SECURE_SSL_REDIRECT=False в production - нужно принудительное HTTPS!")
        else:
            good.append("✅ SECURE_SSL_REDIRECT=True")
        
        if not settings.SESSION_COOKIE_SECURE:
            issues.append("❌ SESSION_COOKIE_SECURE=False - cookies могут быть перехвачены!")
        else:
            good.append("✅ SESSION_COOKIE_SECURE=True")
        
        if not settings.CSRF_COOKIE_SECURE:
            issues.append("❌ CSRF_COOKIE_SECURE=False - CSRF токены могут быть перехвачены!")
        else:
            good.append("✅ CSRF_COOKIE_SECURE=True")
        
        if settings.SECURE_HSTS_SECONDS > 0:
            good.append(f"✅ HSTS включен на {settings.SECURE_HSTS_SECONDS} секунд")
        else:
            warnings.append("⚠️ HSTS не включен - рекомендую для production")
    else:
        print("   (Пропущено: режим разработки)")
    
    # 5. Проверка CORS
    print("5. Проверка CORS настроек...")
    if hasattr(settings, 'CORS_ALLOWED_ORIGINS'):
        cors_origins = settings.CORS_ALLOWED_ORIGINS
        if not cors_origins:
            warnings.append("⚠️ CORS_ALLOWED_ORIGINS не настроен")
        else:
            has_http = any('http://' in origin for origin in cors_origins)
            if has_http and not settings.DEBUG:
                issues.append("❌ CORS использует HTTP вместо HTTPS в production!")
            else:
                good.append(f"✅ CORS настроен ({len(cors_origins)} origins)")
    
    # 6. Проверка наличия хардкод паролей
    print("6. Проверка на жестко зашитые пароли...")
    views_path = os.path.join(settings.BASE_DIR, 'api', 'views.py')
    urls_path = os.path.join(settings.BASE_DIR, 'api', 'urls.py')
    
    found_passwords = []
    for filepath in [views_path, urls_path]:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Ищем подозрительные паттерны
                patterns = [
                    (r"password\s*=\s*['\"][^'\"]+['\"]", "прямое присвоение пароля"),
                    (r"admin123|password123|qwerty|123456", "слабый пароль"),
                    (r"username\s*==\s*['\"][^'\"]+['\"]\s+and\s+password\s*==", "хардкод проверки пароля")
                ]
                for pattern, desc in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        found_passwords.append(f"{os.path.basename(filepath)}: {desc}")
    
    if found_passwords:
        issues.append(f"❌ Найдены потенциально опасные пароли в коде: {', '.join(found_passwords)}")
    else:
        good.append("✅ Жестко зашитые пароли не обнаружены")
    
    # 7. Проверка базы данных
    print("7. Проверка базы данных...")
    db_engine = settings.DATABASES['default']['ENGINE']
    if 'sqlite3' in db_engine:
        if not settings.DEBUG:
            issues.append("❌ SQLite в production - НЕ РЕКОМЕНДУЕТСЯ! Используйте PostgreSQL")
        else:
            warnings.append("⚠️ Используется SQLite - для production замените на PostgreSQL")
    elif 'postgresql' in db_engine:
        good.append("✅ PostgreSQL - отличный выбор для production")
    else:
        warnings.append(f"⚠️ Используется {db_engine} - убедитесь в его надежности")
    
    # 8. Проверка кэша
    print("8. Проверка кэша...")
    if hasattr(settings, 'CACHES'):
        cache_backend = settings.CACHES['default']['BACKEND']
        if 'LocMemCache' in cache_backend and not settings.DEBUG:
            warnings.append("⚠️ Используется LocMemCache в production - рекомендую Redis")
        elif 'Redis' in cache_backend:
            good.append("✅ Redis кэш настроен")
    
    # 9. Проверка пользователей (нет ли дефолтных)
    print("9. Проверка пользователей...")
    try:
        users = User.objects.all()
        if users.count() == 0:
            warnings.append("⚠️ Нет созданных пользователей! Создайте через createsuperuser")
        else:
            # Проверяем нет ли пользователя admin с паролем admin123
            dangerous_users = []
            for user in users:
                if user.username in ['admin', 'test', 'user']:
                    dangerous_users.append(user.username)
            if dangerous_users:
                warnings.append(f"⚠️ Потенциально опасные имена пользователей: {', '.join(dangerous_users)}")
            else:
                good.append(f"✅ Создано {users.count()} пользователей")
    except Exception as e:
        warnings.append(f"⚠️ Не удалось проверить пользователей: {e}")
    
    # 10. Проверка логов
    print("10. Проверка системы логирования...")
    log_dir = os.path.join(settings.BASE_DIR, 'logs')
    if not os.path.exists(log_dir):
        warnings.append("⚠️ Директория логов не существует - будет создана автоматически")
    else:
        good.append("✅ Директория логов существует")
    
    # 11. Проверка версий пакетов
    print("11. Проверка безопасности зависимостей...")
    try:
        print("   Запуск Django安全检查...")
        call_command('check', deploy=True, stdout=open(os.devnull, 'w'))
        good.append("✅ Django security check пройден")
    except Exception as e:
        warnings.append(f"⚠️ Проблемы в безопасности: {e}")
    
    # 12. Проверка CSRF настроек
    print("12. Проверка CSRF настроек...")
    if hasattr(settings, 'CSRF_COOKIE_HTTPONLY') and settings.CSRF_COOKIE_HTTPONLY:
        good.append("✅ CSRF_COOKIE_HTTPONLY=True")
    else:
        issues.append("❌ CSRF_COOKIE_HTTPONLY должен быть True")
    
    if hasattr(settings, 'CSRF_COOKIE_SAMESITE'):
        if settings.CSRF_COOKIE_SAMESITE == 'Strict':
            good.append("✅ CSRF_COOKIE_SAMESITE=Strict")
        elif settings.CSRF_COOKIE_SAMESITE == 'Lax':
            warnings.append("⚠️ CSRF_COOKIE_SAMESITE=Lax - рассмотрите Strict")
        else:
            issues.append(f"❌ CSRF_COOKIE_SAMESITE={settings.CSRF_COOKIE_SAMESITE} - небезопасно")
    
    # 13. Проверка JWT настроек
    print("13. Проверка JWT настроек...")
    if hasattr(settings, 'SIMPLE_JWT'):
        access_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME')
        if access_lifetime:
            minutes = access_lifetime.total_seconds() / 60
            if minutes > 30:
                warnings.append(f"⚠️ JWT access token живет {minutes} минут - рекомендую 15 минут")
            else:
                good.append(f"✅ JWT access token: {minutes} минут")
    
    # Вывод результатов
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print("="*60)
    
    if issues:
        print("\n🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (нужно исправить):")
        for issue in issues:
            print(f"  • {issue}")
    
    if warnings:
        print("\n🟡 ПРЕДУПРЕЖДЕНИЯ (рекомендуется исправить):")
        for warning in warnings:
            print(f"  • {warning}")
    
    if good:
        print("\n✅ ХОРОШИЕ ПРАКТИКИ:")
        for item in good:
            print(f"  • {item}")
    
    # Итоговая оценка
    print("\n" + "="*60)
    if issues:
        print(f"📊 ОЦЕНКА БЕЗОПАСНОСТИ: {max(0, 10 - len(issues) * 2)}/10")
        print("⚠️ Проект НЕ ГОТОВ к production!")
        return False
    elif warnings:
        print("📊 ОЦЕНКА БЕЗОПАСНОСТИ: 7/10")
        print("⚠️ Проект готов к production, но требует доработок")
        return True
    else:
        print("📊 ОЦЕНКА БЕЗОПАСНОСТИ: 10/10")
        print("✅ Проект полностью готов к production!")
        return True

if __name__ == '__main__':
    print("\n🚀 Запуск проверки безопасности...\n")
    success = check_security()
    print("\n" + "="*60)
    sys.exit(0 if success else 1)