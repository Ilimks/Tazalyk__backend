"""Вход в админку для отдела кадров: сотрудник видит и меняет только раздел «Вакансии».

    python manage.py create_hr_user                   # логин hr_manager
    python manage.py create_hr_user --reset-password  # новый пароль уже созданному сотруднику

Пароль берётся из HR_MANAGER_PASSWORD (переменная окружения или строка в .env).
Если его нет — создаётся случайный и печатается один раз. Других пользователей команда не трогает
(в отличие от create_users.py, который сбрасывает пароли всем).
"""
import os
import secrets
import string

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

HR_GROUP = 'hr_managers'
PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_password(length=16):
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


class Command(BaseCommand):
    help = 'Создаёт сотрудника отдела кадров (доступ только к вакансиям)'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='hr_manager', help='Логин (по умолчанию hr_manager)')
        parser.add_argument('--reset-password', action='store_true', help='Задать пароль заново, если сотрудник уже есть')

    def handle(self, *args, username, reset_password, **options):
        group, _ = Group.objects.get_or_create(name=HR_GROUP)
        user, created = User.objects.get_or_create(username=username)

        if user.is_superuser:
            raise CommandError(f'«{username}» — суперпользователь, ему нельзя оставить только вакансии. Выберите другой логин.')

        # только отдел кадров: никаких других разделов и входа в /admin/ Django
        user.is_staff = False
        user.groups.set([group])

        message = 'пароль не менялся (новый: --reset-password)'
        if created or reset_password:
            env_password = os.environ.get('HR_MANAGER_PASSWORD') or settings.ENV.get('HR_MANAGER_PASSWORD')
            password = env_password or generate_password()
            try:
                validate_password(password, user)
            except ValidationError as error:
                raise CommandError('Пароль из HR_MANAGER_PASSWORD слишком простой: ' + ' '.join(error.messages))
            user.set_password(password)
            message = 'пароль взят из HR_MANAGER_PASSWORD' if env_password else f'пароль: {password}  (сохраните его — больше он не покажется)'

        user.save()
        action = 'Создан' if created else 'Обновлён'
        self.stdout.write(self.style.SUCCESS(f'{action} сотрудник отдела кадров «{username}», {message}'))
