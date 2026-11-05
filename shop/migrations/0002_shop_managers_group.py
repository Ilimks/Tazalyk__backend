from django.db import migrations

GROUP_NAME = 'shop_managers'


def create_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=GROUP_NAME)


def delete_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):
    """Группа «Менеджеры магазина»: управляют товарами и заказами (права проверяет shop/permissions.py)"""

    dependencies = [
        ('shop', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_group, delete_group),
    ]
