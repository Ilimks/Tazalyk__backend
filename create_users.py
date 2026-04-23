import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tazalyk.settings')
django.setup()

from django.contrib.auth.models import User, Group

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
    
    # Создаем пользователей (ЗАМЕНИТЕ ПАРОЛИ НА СВОИ!)
    users = [
        {'username': 'admin', 'password': 'admin3257!@K', 'email': 'admin@tazalyk.kg', 'is_superuser': True, 'is_staff': True, 'groups': []},
        {'username': 'content_manager', 'password': 'content_manager!@Altuha', 'email': 'content@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['content_managers']},
        {'username': 'procurement_manager', 'password': 'procurement_manager!@AidarZakupki', 'email': 'procurement@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['procurement_managers']},
        {'username': 'legal_manager', 'password': 'legal_manager!@Urists', 'email': 'legal@tazalyk.kg', 'is_superuser': False, 'is_staff': True, 'groups': ['legal_managers']},
        {'username': 'viewer', 'password': 'viewer123321gas@!', 'email': 'viewer@tazalyk.kg', 'is_superuser': False, 'is_staff': False, 'groups': ['viewers']},
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