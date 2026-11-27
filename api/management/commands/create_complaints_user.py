import os

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from .create_hr_user import generate_password

COMPLAINTS_GROUP = 'complaints_managers'


class Command(BaseCommand):
    help = 'Создаёт сотрудника, который разбирает жалобы (доступ только к жалобам)'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='complaints_manager', help='Логин (по умолчанию complaints_manager)')
        parser.add_argument('--reset-password', action='store_true', help='Задать пароль заново, если сотрудник уже есть')

    def handle(self, *args, username, reset_password, **options):
        group, _ = Group.objects.get_or_create(name=COMPLAINTS_GROUP)
        user, created = User.objects.get_or_create(username=username)

        if user.is_superuser:
            raise CommandError(f'«{username}» — суперпользователь, ему нельзя оставить только жалобы. Выберите другой логин.')

        user.is_staff = False
        user.groups.set([group])

        message = 'пароль не менялся (новый: --reset-password)'
        if created or reset_password:
            env_password = os.environ.get('COMPLAINTS_MANAGER_PASSWORD') or settings.ENV.get('COMPLAINTS_MANAGER_PASSWORD')
            password = env_password or generate_password()
            try:
                validate_password(password, user)
            except ValidationError as error:
                raise CommandError('Пароль из COMPLAINTS_MANAGER_PASSWORD слишком простой: ' + ' '.join(error.messages))
            user.set_password(password)
            message = (
                'пароль взят из COMPLAINTS_MANAGER_PASSWORD' if env_password
                else f'пароль: {password}  (сохраните его — больше он не покажется)'
            )

        user.save()
        action = 'Создан' if created else 'Обновлён'
        self.stdout.write(self.style.SUCCESS(f'{action} сотрудник по жалобам «{username}», {message}'))
