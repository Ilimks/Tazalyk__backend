import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tazalyk.settings')
django.setup()

from django.contrib.auth.models import User, Group
from dotenv import load_dotenv
from pathlib import Path

# Загружаем .env файл
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

def create_users_and_groups():
    # Создаем группы
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
    
    # Создаем пользователей (пароли из .env)
    users = [
        {'username': 'admin', 'password': os.getenv('ADMIN_PASSWORD', 'admin3257!@K'), 'email': 'admin@tazalyk.kg', 'is_superuser': True, 'is_staff': True, 'groups': []},
        {'username': 'content_manager', 'password': os.getenv('CONTENT_MANAGER_PASSWORD', 'content_manager!@Altuha'), 'email': 'content@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['content_managers']},
        {'username': 'procurement_manager', 'password': os.getenv('PROCUREMENT_MANAGER_PASSWORD', 'procurement_manager!@AidarZakupki'), 'email': 'procurement@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['procurement_managers']},
        {'username': 'legal_manager', 'password': os.getenv('LEGAL_MANAGER_PASSWORD', 'legal_manager!@Urists'), 'email': 'legal@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['legal_managers']},
        {'username': 'viewer', 'password': os.getenv('VIEWER_PASSWORD', 'viewer123321gas@!'), 'email': 'viewer@tazalyk.kg', 'is_superuser': False, 'is_staff': False, 'groups': ['viewers']},
    ]
    
    for user_data in users:
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data['email'],
                'is_superuser': user_data['is_superuser'],
                'is_staff': user_data['is_staff'],
            }
        )
        
        if created:
            user.set_password(user_data['password'])
            user.save()
            print(f"✅ Создан пользователь: {user_data['username']}")
        else:
            print(f"⚠️ Пользователь уже существует: {user_data['username']}")
        
        # Обновляем пароль (если нужно)
        user.set_password(user_data['password'])
        user.save()
        
        # Добавляем в группы
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