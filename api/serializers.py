import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import Throttled
from shop.contacts import PHONE_RE, international_phone, is_valid_phone
from .media_files import StoredFilesMixin
from .media_validation import RESUME_MAX_BYTES, detect_resume_type, is_safe_docx, validate_media, validate_media_list
from .models import (
    Complaint, ComplaintPhoto, Video, Photo, News, Procurement, LocalAct, Legislation, Vacancy, VacancyApplication,
)

logger = logging.getLogger(__name__)

class VideoSerializer(StoredFilesMixin, serializers.ModelSerializer):
    file_folder = 'videos'
    file_fields = ('main_video_url', 'thumbnail')
    file_list_fields = ('gallery_videos',)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Video
        fields = ['id', 'main_video_url', 'gallery_videos', 'thumbnail', 'date', 'created_at', 'updated_at']

    def validate_main_video_url(self, value):
        return validate_media(value, 'video')

    def validate_gallery_videos(self, value):
        return validate_media_list(value, 'video')

    def validate_thumbnail(self, value):
        return validate_media(value, 'image')

class PhotoSerializer(StoredFilesMixin, serializers.ModelSerializer):
    file_folder = 'photos'
    file_fields = ('main_image',)
    file_list_fields = ('gallery_images',)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Photo
        fields = ['id', 'main_image', 'gallery_images', 'date', 'created_at', 'updated_at']

    def validate_main_image(self, value):
        return validate_media(value, 'image')

    def validate_gallery_images(self, value):
        return validate_media_list(value, 'image')

class NewsSerializer(StoredFilesMixin, serializers.ModelSerializer):
    file_folder = 'news'
    file_fields = ('image',)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = News
        fields = [
            'id', 
            'title_ru', 'title_ky',
            'description_ru', 'description_ky',
            'image', 'date', 
            'created_at', 'updated_at'
        ]

    def validate_image(self, value):
        return validate_media(value, 'image')

class ProcurementSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Procurement
        fields = ['id', 'number', 'contractNumber', 'supplier', 'type', 'method', 'status', 'date', 'amount', 'created_at', 'updated_at']
        read_only_fields = ['number']

# ========== ДОКУМЕНТЫ ==========
class LocalActSerializer(StoredFilesMixin, serializers.ModelSerializer):
    file_folder = 'documents'
    file_fields = ('file_url',)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = LocalAct
        fields = ['id', 'title', 'file_url', 'file_name', 'file_size', 'date', 'created_at', 'updated_at']

    def validate_file_url(self, value):
        return validate_media(value, 'document')

class LegislationSerializer(StoredFilesMixin, serializers.ModelSerializer):
    file_folder = 'documents'
    file_fields = ('file_url',)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Legislation
        fields = ['id', 'title', 'file_url', 'file_name', 'file_size', 'date', 'created_at', 'updated_at']

    def validate_file_url(self, value):
        return validate_media(value, 'document')

# ========== ВАКАНСИИ ==========
class VacancySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Vacancy
        fields = [
            'id',
            'title_ru', 'title_ky',
            'description_ru', 'description_ky',
            'requirements_ru', 'requirements_ky',
            'schedule_ru', 'schedule_ky',
            'salary_from', 'salary_to',
            'is_active',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        # при PATCH (например, только is_active) второе значение берётся из сохранённой вакансии
        salary_from = attrs.get('salary_from', getattr(self.instance, 'salary_from', None))
        salary_to = attrs.get('salary_to', getattr(self.instance, 'salary_to', None))
        if salary_from is not None and salary_to is not None and salary_to < salary_from:
            raise serializers.ValidationError({'salary_to': 'Зарплата «до» не может быть меньше зарплаты «от».'})
        return attrs


# ========== ОТКЛИКИ НА ВАКАНСИИ ==========
class VacancyApplicationCreateSerializer(serializers.Serializer):
    """Отклик с сайта: все поля проверяются здесь, браузеру не доверяем"""

    vacancy = serializers.PrimaryKeyRelatedField(queryset=Vacancy.objects.filter(is_active=True))
    full_name = serializers.CharField(min_length=2, max_length=150, trim_whitespace=True)
    phone = serializers.CharField(max_length=30, trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, trim_whitespace=True)
    resume = serializers.FileField(allow_empty_file=False)
    consent = serializers.BooleanField()
    # ловушка для ботов: поле скрыто на сайте, человек его не заполнит
    website = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        if not PHONE_RE.match(value) or not is_valid_phone(value):
            raise serializers.ValidationError('Укажите номер телефона, например +996 700 123 456.')
        return value

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError('Нужно согласие на обработку персональных данных.')
        return value

    def validate_resume(self, file):
        if file.size > RESUME_MAX_BYTES:
            raise serializers.ValidationError('Файл больше 5 МБ.')
        content = file.read()
        kind = detect_resume_type(content)
        if kind is None or (kind[0] == 'docx' and not is_safe_docx(content)):
            raise serializers.ValidationError('Подойдёт файл PDF, DOCX, JPG или PNG.')
        return {'content': content, 'extension': kind[0], 'type': kind[1]}

    def validate(self, data):
        since = timezone.now() - timedelta(hours=24)
        phone = international_phone(data['phone'])
        recent_phones = VacancyApplication.objects.filter(
            vacancy=data['vacancy'], created_at__gte=since,
        ).values_list('phone', flat=True)
        if phone in map(international_phone, recent_phones):
            raise serializers.ValidationError({'duplicate': 'Вы уже отправили резюме на эту вакансию.'})

        # общий предел на случай рассылки с разных адресов: база не должна заполниться чужими файлами
        uploaded = VacancyApplication.objects.filter(created_at__gte=since).aggregate(
            total=Sum('resume_size'),
        )['total'] or 0
        if uploaded >= settings.APPLICATIONS_DAILY_BYTES:
            logger.warning('Отклики: дневной предел загрузки исчерпан')
            raise Throttled(detail='Сейчас отправить резюме не получится. Попробуйте завтра.')
        return data

    def create(self, validated_data):
        vacancy = validated_data['vacancy']
        resume = validated_data['resume']
        full_name = validated_data['full_name']
        # имя файла собираем сами: так кадровику проще, а чужие символы в него не попадут
        safe_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', ' ', full_name).strip()
        return VacancyApplication.objects.create(
            vacancy=vacancy,
            vacancy_title=vacancy.title_ru,
            full_name=full_name,
            phone=validated_data['phone'],
            email=validated_data.get('email', ''),
            comment=validated_data.get('comment', ''),
            resume_content=resume['content'],
            resume_name=f"Резюме {safe_name}.{resume['extension']}",
            resume_type=resume['type'],
            resume_size=len(resume['content']),
        )


class VacancyApplicationSerializer(serializers.ModelSerializer):
    """Для отдела кадров. Сам файл сюда не входит: его скачивают отдельным запросом"""

    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = VacancyApplication
        fields = [
            'id', 'vacancy', 'vacancy_title', 'full_name', 'phone', 'email', 'comment',
            'resume_name', 'resume_size', 'status', 'status_label', 'hr_note', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'vacancy', 'vacancy_title', 'full_name', 'phone', 'email', 'comment',
            'resume_name', 'resume_size', 'created_at', 'updated_at',
        ]


# ========== ЖАЛОБЫ ==========
COMPLAINT_MAX_PHOTOS = 5
COMPLAINT_PHOTO_MAX_BYTES = 5 * 1024 * 1024
# столько же пропускает сайт: Gmail не примет письмо больше
COMPLAINT_PHOTOS_MAX_TOTAL = 15 * 1024 * 1024

# тип фото — по первым байтам, как на сайте; имени и типу из запроса не верим
COMPLAINT_PHOTO_TYPES = (
    ('image/jpeg', lambda head: head[:3] == b'\xff\xd8\xff'),
    ('image/png', lambda head: head[:8] == b'\x89PNG\r\n\x1a\n'),
    ('image/webp', lambda head: head[:4] == b'RIFF' and head[8:12] == b'WEBP'),
    ('image/heic', lambda head: head[4:8] == b'ftyp' and head[8:12] in (b'heic', b'heix', b'hevc', b'mif1', b'msf1')),
)


def detect_photo_type(content):
    return next((mime for mime, test in COMPLAINT_PHOTO_TYPES if test(content[:16])), None)


class ComplaintCreateSerializer(serializers.Serializer):
    """Жалоба от сервера сайта. Капча, почта и длина полей там уже проверены,
    здесь — повторная проверка: в базу не должно попасть то, что админка не покажет"""

    complaint_type = serializers.ChoiceField(choices=Complaint.TYPE_CHOICES)
    full_name = serializers.CharField(max_length=200)
    email = serializers.CharField(max_length=254)
    phone = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=300)
    description = serializers.CharField(max_length=10000)
    incident_date = serializers.DateField(required=False, allow_null=True)
    incident_location = serializers.CharField(max_length=300, required=False, allow_blank=True)
    photos = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False),
        required=False,
        max_length=COMPLAINT_MAX_PHOTOS,
    )

    def validate_photos(self, files):
        photos = []
        for file in files:
            if file.size > COMPLAINT_PHOTO_MAX_BYTES:
                raise serializers.ValidationError('Фото больше 5 МБ.')
            content = file.read()
            content_type = detect_photo_type(content)
            if content_type is None:
                raise serializers.ValidationError('Подойдут фото JPG, PNG, WEBP или HEIC.')
            photos.append({'content': content, 'content_type': content_type})
        if sum(len(photo['content']) for photo in photos) > COMPLAINT_PHOTOS_MAX_TOTAL:
            raise serializers.ValidationError('Все фото вместе больше 15 МБ.')
        return photos

    def create(self, validated_data):
        photos = validated_data.pop('photos', [])
        note = ''
        if photos and self._daily_limit_reached(photos):
            # жалобу важнее сохранить, чем фото: они всё равно есть в письме
            logger.warning('Жалобы: дневной предел фото исчерпан, жалоба сохранена без фото')
            photos = []
            note = 'Фото не сохранены: за сутки прислали слишком много. Они есть в письме с этой жалобой.'

        complaint = Complaint.objects.create(**validated_data, manager_note=note)
        ComplaintPhoto.objects.bulk_create([
            ComplaintPhoto(
                complaint=complaint,
                content=photo['content'],
                content_type=photo['content_type'],
                size=len(photo['content']),
                position=index,
            )
            for index, photo in enumerate(photos)
        ])
        return complaint

    @staticmethod
    def _daily_limit_reached(photos):
        since = timezone.now() - timedelta(hours=24)
        stored = ComplaintPhoto.objects.filter(complaint__created_at__gte=since).aggregate(total=Sum('size'))['total'] or 0
        return stored + sum(len(photo['content']) for photo in photos) > settings.COMPLAINTS_DAILY_BYTES


class ComplaintPhotoSerializer(serializers.ModelSerializer):
    """Без самого файла: его админка скачивает отдельным запросом"""

    class Meta:
        model = ComplaintPhoto
        fields = ['id', 'content_type', 'size']


class ComplaintSerializer(serializers.ModelSerializer):
    """Для сотрудников. Менять можно только статус и свою заметку"""

    type_label = serializers.CharField(source='get_complaint_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    photos = ComplaintPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Complaint
        fields = [
            'id', 'complaint_type', 'type_label', 'full_name', 'email', 'phone', 'subject', 'description',
            'incident_date', 'incident_location', 'photos', 'status', 'status_label', 'manager_note',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'complaint_type', 'full_name', 'email', 'phone', 'subject', 'description',
            'incident_date', 'incident_location', 'created_at', 'updated_at',
        ]
        extra_kwargs = {'manager_note': {'max_length': 5000}}
