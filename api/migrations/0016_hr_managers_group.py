from django.db import migrations

GROUP_NAME = 'hr_managers'


def create_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=GROUP_NAME)


def delete_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):
    """Группа «Отдел кадров»: управляет только вакансиями (права проверяет api/views.py, SECTION_GROUPS)"""

    dependencies = [
        ('api', '0015_vacancy'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_group, delete_group),
    ]
