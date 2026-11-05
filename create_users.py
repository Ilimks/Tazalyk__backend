import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tazalyk.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User, Group


def require_password(name):
    """Пароль берётся только из настроек: значения по умолчанию в коде попали в открытый репозиторий"""
    password = settings.ENV.get(name)
    if not password:
        raise SystemExit(f'Задайте {name} в .env: без него сотрудника не создать')
    return password


def create_users_and_groups():
    groups = {
        'content_managers': 'Менеджеры контента',
        'procurement_managers': 'Менеджеры закупок',
        'legal_managers': 'Юридические менеджеры',
        'viewers': 'Просмотрщики',
    }

    for group_name, description in groups.items():
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            print(f"✅ Создана группа: {group_name}")

    users = [
        {'username': 'admin', 'password_env': 'ADMIN_PASSWORD', 'email': 'admin@tazalyk.kg', 'is_superuser': True, 'is_staff': True, 'groups': []},
        {'username': 'content_manager', 'password_env': 'CONTENT_MANAGER_PASSWORD', 'email': 'content@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['content_managers']},
        {'username': 'procurement_manager', 'password_env': 'PROCUREMENT_MANAGER_PASSWORD', 'email': 'procurement@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['procurement_managers']},
        {'username': 'legal_manager', 'password_env': 'LEGAL_MANAGER_PASSWORD', 'email': 'legal@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['legal_managers']},
        {'username': 'viewer', 'password_env': 'VIEWER_PASSWORD', 'email': 'viewer@tazalyk.kg', 'is_superuser': False, 'is_staff': False, 'groups': ['viewers']},
    ]

    for user_data in users:
        user = User.objects.filter(username=user_data['username']).first()
        if user:
            # пароль существующего сотрудника не трогаем: иначе скрипт отменял бы смену паролей
            print(f"⚠️ Пользователь уже существует: {user_data['username']}")
        else:
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                is_superuser=user_data['is_superuser'],
                is_staff=user_data['is_staff'],
            )
            user.set_password(require_password(user_data['password_env']))
            user.save()
            print(f"✅ Создан пользователь: {user_data['username']}")

        for group_name in user_data['groups']:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            print(f"   → Добавлен в группу: {group_name}")

if __name__ == '__main__':
    print("=" * 50)
    print("СОЗДАНИЕ ПОЛЬЗОВАТЕЛЕЙ И ГРУПП")
    print("=" * 50)
    create_users_and_groups()
    print("=" * 50)
    print("ГОТОВО!")
