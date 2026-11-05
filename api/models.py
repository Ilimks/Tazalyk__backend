from django.core.validators import MaxValueValidator
from django.db import models
import uuid
import time

# ========== ВИДЕО ==========
class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    main_video_url = models.TextField(verbose_name="Главное видео (base64)")
    gallery_videos = models.JSONField(default=list, blank=True, verbose_name="Дополнительные видео")
    thumbnail = models.TextField(blank=True, null=True, verbose_name="Превью (base64)")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Видео'
        verbose_name_plural = 'Видео'
    
    def __str__(self):
        return f"Видео от {self.date}"

# ========== ФОТО ==========
class Photo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    main_image = models.TextField(verbose_name="Главное фото (base64)")
    gallery_images = models.JSONField(default=list, blank=True, verbose_name="Дополнительные фото")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Фото'
        verbose_name_plural = 'Фото'
    
    def __str__(self):
        return f"Фото от {self.date}"

# ========== НОВОСТИ ==========
class News(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title_ru = models.CharField(max_length=255, verbose_name="Название (Русский)")
    description_ru = models.TextField(verbose_name="Описание (Русский)")
    title_ky = models.CharField(max_length=255, verbose_name="Название (Кыргызча)", blank=True, null=True)
    description_ky = models.TextField(verbose_name="Описание (Кыргызча)", blank=True, null=True)
    image = models.TextField(blank=True, null=True, verbose_name="Изображение (base64)")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
    
    def __str__(self):
        return self.title_ru

# ========== ЗАКУПКИ ==========
class Procurement(models.Model):
    TYPE_CHOICES = [
        ('goods', 'Товар'),
        ('services', 'Услуга'),
        ('works', 'Работа'),
    ]
    METHOD_CHOICES = [
        ('direct', 'Прямое заключение договора'),
        ('quotation', 'Запрос котировок'),
        ('simple', 'Простейшая закупка'),
        ('tender', 'Конкурс'),
    ]
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=100, blank=True, verbose_name="Номер закупки")
    contractNumber = models.CharField(max_length=100, verbose_name="Номер контракта")
    supplier = models.CharField(max_length=255, verbose_name="Поставщик")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='goods', verbose_name="Тип")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='direct', verbose_name="Способ закупки")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Статус")
    date = models.DateField(verbose_name="Дата")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Сумма")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Закупка'
        verbose_name_plural = 'Закупки'
    
    def save(self, *args, **kwargs):
        if not self.number:
            last_procurement = Procurement.objects.exclude(id=self.id).order_by('-created_at').first()
            if last_procurement and last_procurement.number:
                try:
                    last_number = int(last_procurement.number)
                    self.number = str(last_number + 1)
                except ValueError:
                    self.number = '1'
            else:
                self.number = '1'
        if not self.id:
            self.id = str(int(time.time() * 1000))
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.number} - {self.contractNumber} - {self.supplier}"

# ========== БАЗОВАЯ МОДЕЛЬ ДЛЯ ДОКУМЕНТОВ ==========
class BaseDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500, verbose_name="Название документа")
    file_url = models.TextField(verbose_name="Файл (base64)")
    file_name = models.CharField(max_length=255, verbose_name="Имя файла")
    file_size = models.BigIntegerField(default=0, verbose_name="Размер файла (байт)")
    date = models.DateField(verbose_name="Дата публикации")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        abstract = True
        ordering = ['-date', '-created_at']

# ========== ЛОКАЛЬНЫЕ АКТЫ ==========
class LocalAct(BaseDocument):
    class Meta:
        verbose_name = 'Локальный акт'
        verbose_name_plural = 'Локальные акты'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return self.title

# ========== ЗАКОНОДАТЕЛЬСТВО КР ==========
class Legislation(BaseDocument):
    class Meta:
        verbose_name = 'Законодательство'
        verbose_name_plural = 'Законодательство КР'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.title

# ========== ВАКАНСИИ ==========
class Vacancy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title_ru = models.CharField(max_length=200, verbose_name="Должность (Русский)")
    title_ky = models.CharField(max_length=200, blank=True, verbose_name="Должность (Кыргызча)")
    description_ru = models.TextField(blank=True, verbose_name="Обязанности и условия (Русский)")
    description_ky = models.TextField(blank=True, verbose_name="Обязанности и условия (Кыргызча)")
    # каждая строка — отдельный пункт списка на сайте
    requirements_ru = models.TextField(blank=True, verbose_name="Требования (Русский)")
    requirements_ky = models.TextField(blank=True, verbose_name="Требования (Кыргызча)")
    schedule_ru = models.CharField(max_length=200, blank=True, verbose_name="График работы (Русский)")
    schedule_ky = models.CharField(max_length=200, blank=True, verbose_name="График работы (Кыргызча)")
    # зарплата в сомах; оба поля пустые — «по договорённости»
    salary_from = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000_000)], verbose_name="Зарплата от, сом"
    )
    salary_to = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000_000)], verbose_name="Зарплата до, сом"
    )
    # неактивная вакансия скрыта с сайта, но остаётся в админке
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'
        indexes = [
            models.Index(fields=['is_active', '-created_at'], name='api_vacancy_active_created'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(salary_from__isnull=True)
                | models.Q(salary_to__isnull=True)
                | models.Q(salary_to__gte=models.F('salary_from')),
                name='api_vacancy_salary_range',
            ),
        ]

    def __str__(self):
        return self.title_ru