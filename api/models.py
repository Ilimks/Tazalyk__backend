from django.db import models
from django.utils import timezone
import uuid

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


class News(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
        # Генерация номера закупки при создании (простая нумерация: 1, 2, 3...)
        if not self.number:
            # Получаем последнюю закупку
            last_procurement = Procurement.objects.exclude(id=self.id).order_by('-created_at').first()
            
            if last_procurement and last_procurement.number:
                # Если есть предыдущий номер, увеличиваем его
                try:
                    last_number = int(last_procurement.number)
                    self.number = str(last_number + 1)
                except ValueError:
                    # Если номер не число, начинаем с 1
                    self.number = '1'
            else:
                # Если это первая закупка
                self.number = '1'
        
        # Генерация ID если его нет
        if not self.id:
            self.id = str(int(time.time() * 1000))
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.number} - {self.contractNumber} - {self.supplier}"
    
    def format_amount(self):
        return f"{self.amount:,.0f} сом".replace(',', ' ')


# ========== БАЗОВАЯ МОДЕЛЬ ДЛЯ ДОКУМЕНТОВ ==========
class BaseDocument(models.Model):
    """Абстрактная базовая модель для документов"""
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
    """Локальные акты предприятия"""
    
    class Meta:
        verbose_name = 'Локальный акт'
        verbose_name_plural = 'Локальные акты'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return self.title


# ========== ЗАКОНОДАТЕЛЬСТВО КР ==========
class Legislation(BaseDocument):
    """Законы и нормативные акты Кыргызской Республики"""
    
    class Meta:
        verbose_name = 'Законодательство'
        verbose_name_plural = 'Законодательство КР'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return self.title