from django.db import models

class Video(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    main_video_url = models.TextField(verbose_name="Главное видео (base64)")  # Изменено с URLField на TextField
    gallery_videos = models.JSONField(default=list, blank=True, verbose_name="Дополнительные видео")  # Массив base64 строк
    thumbnail = models.TextField(blank=True, null=True, verbose_name="Превью (base64)")  # Изменено на TextField
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Видео'
        verbose_name_plural = 'Видео'
    
    def __str__(self):
        return self.title
    
    def get_video_preview(self):
        """Получить превью видео (если есть)"""
        if self.thumbnail:
            return self.thumbnail
        return "/assets/images/placeholder-video.jpg"


class Photo(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
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
        return self.title
    
    def get_all_images(self):
        """Получить все фото (главное + галерея)"""
        return [self.main_image] + (self.gallery_images or [])


class News(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    image = models.TextField(blank=True, null=True, verbose_name="Изображение (base64)")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
    
    def __str__(self):
        return self.title


# models.py
class Procurement(models.Model):
    # Типы закупки (что закупается)
    TYPE_CHOICES = [
        ('goods', 'Товар'),
        ('services', 'Услуга'),
        ('works', 'Работа'),
    ]
    
    # Методы закупки (как закупается)
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
    
    id = models.CharField(max_length=50, primary_key=True)
    number = models.CharField(max_length=100, verbose_name="Номер закупки")
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
    
    def __str__(self):
        return f"{self.contractNumber} - {self.supplier}"
    
    def format_amount(self):
        return f"{self.amount:,.0f} сом".replace(',', ' ')


class Vacancy(models.Model):
    STATUS_CHOICES = [
        ('open', 'Открыта'),
        ('closed', 'Закрыта'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True)
    title = models.CharField(max_length=255, verbose_name="Название вакансии")
    salary_from = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="Зарплата от")
    salary_to = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="Зарплата до")
    schedule = models.CharField(max_length=100, verbose_name="График работы")
    experience = models.CharField(max_length=100, verbose_name="Опыт работы")
    description = models.TextField(verbose_name="Описание")
    requirements = models.JSONField(default=list, verbose_name="Требования")
    responsibilities = models.JSONField(default=list, verbose_name="Обязанности")
    conditions = models.JSONField(default=list, verbose_name="Условия")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Статус")
    published_at = models.DateField(verbose_name="Дата публикации")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'
    
    def __str__(self):
        return self.title
    
    def get_salary_display(self):
        """Форматировать зарплату"""
        if self.salary_from and self.salary_to:
            return f"{self.salary_from:,.0f} - {self.salary_to:,.0f} сом".replace(',', ' ')
        elif self.salary_from:
            return f"от {self.salary_from:,.0f} сом".replace(',', ' ')
        elif self.salary_to:
            return f"до {self.salary_to:,.0f} сом".replace(',', ' ')
        return "Договорная"