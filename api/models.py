from django.core.validators import MaxValueValidator
from django.db import models
import uuid
import time

class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    main_video_url = models.TextField(verbose_name="Главное видео")
    gallery_videos = models.JSONField(default=list, blank=True, verbose_name="Дополнительные видео")
    thumbnail = models.TextField(blank=True, null=True, verbose_name="Превью")
    caption_ru = models.CharField(max_length=160, blank=True, default='', verbose_name="Подпись (Русский)")
    caption_ky = models.CharField(max_length=160, blank=True, default='', verbose_name="Подпись (Кыргызча)")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Видео'
        verbose_name_plural = 'Видео'
    
    def __str__(self):
        return self.caption_ru or f"Видео от {self.date}"

class Photo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    main_image = models.TextField(verbose_name="Главное фото")
    gallery_images = models.JSONField(default=list, blank=True, verbose_name="Дополнительные фото")
    caption_ru = models.CharField(max_length=160, blank=True, default='', verbose_name="Подпись (Русский)")
    caption_ky = models.CharField(max_length=160, blank=True, default='', verbose_name="Подпись (Кыргызча)")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Фото'
        verbose_name_plural = 'Фото'
    
    def __str__(self):
        return self.caption_ru or f"Фото от {self.date}"

class News(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title_ru = models.CharField(max_length=255, verbose_name="Название (Русский)")
    description_ru = models.TextField(verbose_name="Описание (Русский)")
    title_ky = models.CharField(max_length=255, verbose_name="Название (Кыргызча)", blank=True, null=True)
    description_ky = models.TextField(verbose_name="Описание (Кыргызча)", blank=True, null=True)
    image = models.TextField(blank=True, null=True, verbose_name="Изображение")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
    
    def __str__(self):
        return self.title_ru

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

class BaseDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500, verbose_name="Название документа")
    file_url = models.TextField(verbose_name="Файл")
    file_name = models.CharField(max_length=255, verbose_name="Имя файла")
    file_size = models.BigIntegerField(default=0, verbose_name="Размер файла (байт)")
    date = models.DateField(verbose_name="Дата публикации")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        abstract = True
        ordering = ['-date', '-created_at']

class LocalAct(BaseDocument):
    class Meta:
        verbose_name = 'Локальный акт'
        verbose_name_plural = 'Локальные акты'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return self.title

class Legislation(BaseDocument):
    class Meta:
        verbose_name = 'Законодательство'
        verbose_name_plural = 'Законодательство КР'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.title

class Vacancy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title_ru = models.CharField(max_length=200, verbose_name="Должность (Русский)")
    title_ky = models.CharField(max_length=200, blank=True, verbose_name="Должность (Кыргызча)")
    description_ru = models.TextField(blank=True, verbose_name="Обязанности и условия (Русский)")
    description_ky = models.TextField(blank=True, verbose_name="Обязанности и условия (Кыргызча)")
    requirements_ru = models.TextField(blank=True, verbose_name="Требования (Русский)")
    requirements_ky = models.TextField(blank=True, verbose_name="Требования (Кыргызча)")
    schedule_ru = models.CharField(max_length=200, blank=True, verbose_name="График работы (Русский)")
    schedule_ky = models.CharField(max_length=200, blank=True, verbose_name="График работы (Кыргызча)")
    salary_from = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000_000)], verbose_name="Зарплата от, сом"
    )
    salary_to = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000_000)], verbose_name="Зарплата до, сом"
    )
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


class VacancyApplication(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('in_review', 'На рассмотрении'),
        ('invited', 'Приглашён'),
        ('hired', 'Принят'),
        ('rejected', 'Отказ'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vacancy = models.ForeignKey(
        Vacancy, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applications', verbose_name="Вакансия",
    )
    vacancy_title = models.CharField(max_length=200, verbose_name="Название вакансии")
    full_name = models.CharField(max_length=150, verbose_name="ФИО")
    phone = models.CharField(max_length=30, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Электронная почта")
    comment = models.TextField(blank=True, verbose_name="Комментарий кандидата")
    resume_content = models.BinaryField(verbose_name="Файл резюме")
    resume_name = models.CharField(max_length=255, verbose_name="Имя файла")
    resume_type = models.CharField(max_length=100, verbose_name="Тип файла")
    resume_size = models.PositiveIntegerField(verbose_name="Размер файла, байт")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Статус")
    hr_note = models.TextField(blank=True, verbose_name="Заметка отдела кадров")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отклика")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Отклик на вакансию'
        verbose_name_plural = 'Отклики на вакансии'
        indexes = [
            models.Index(fields=['status', '-created_at'], name='api_application_status_created'),
        ]

    def __str__(self):
        return f'{self.full_name} — {self.vacancy_title}'


class Complaint(models.Model):
    TYPE_CHOICES = [
        ('waste_issue', 'Проблема с вывозом отходов'),
        ('billing_error', 'Неправильное начисление за вывоз мусора'),
        ('service_quality', 'Качество услуг'),
        ('employee_complaint', 'Жалоба на сотрудника'),
        ('other', 'Другое'),
    ]
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('resolved', 'Решена'),
        ('rejected', 'Отклонена'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    complaint_type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name="Тип обращения")
    full_name = models.CharField(max_length=200, verbose_name="ФИО")
    email = models.CharField(max_length=254, verbose_name="Электронная почта")
    phone = models.CharField(max_length=50, verbose_name="Телефон")
    subject = models.CharField(max_length=300, verbose_name="Тема")
    description = models.TextField(verbose_name="Суть жалобы")
    incident_date = models.DateField(null=True, blank=True, verbose_name="Дата происшествия")
    incident_location = models.CharField(max_length=300, blank=True, verbose_name="Место происшествия")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Статус")
    manager_note = models.TextField(blank=True, verbose_name="Заметка сотрудника")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата поступления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Жалоба'
        verbose_name_plural = 'Жалобы'
        indexes = [
            models.Index(fields=['status', '-created_at'], name='api_complaint_status_created'),
            models.Index(fields=['complaint_type', '-created_at'], name='api_complaint_type_created'),
        ]

    def __str__(self):
        return f'{self.full_name} — {self.subject}'


class ComplaintPhoto(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='photos', verbose_name="Жалоба")
    content = models.BinaryField(verbose_name="Файл")
    content_type = models.CharField(max_length=50, verbose_name="Тип файла")
    size = models.PositiveIntegerField(verbose_name="Размер, байт")
    position = models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ['position', 'id']
        verbose_name = 'Фото к жалобе'
        verbose_name_plural = 'Фото к жалобам'

    def __str__(self):
        return f'Фото {self.position + 1} — {self.complaint_id}'


class SiteSettings(models.Model):
    winter_effects = models.BooleanField('Снег и Дед Мороз на сайте', default=False)
    updated_at = models.DateTimeField('Изменено', auto_now=True)

    class Meta:
        verbose_name = 'Оформление сайта'
        verbose_name_plural = 'Оформление сайта'

    def __str__(self):
        return 'Оформление сайта'

    @classmethod
    def load(cls):
        settings_row, _ = cls.objects.get_or_create(pk=1)
        return settings_row
