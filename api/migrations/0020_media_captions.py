from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0019_complaints_managers_group'),
    ]

    operations = [
        migrations.AddField(
            model_name=model,
            name=name,
            field=models.CharField(blank=True, default='', max_length=160, verbose_name=label),
        )
        for model in ('photo', 'video')
        for name, label in (('caption_ru', 'Подпись (Русский)'), ('caption_ky', 'Подпись (Кыргызча)'))
    ]
