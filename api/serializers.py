from rest_framework import serializers
from .media_validation import validate_media, validate_media_list
from .models import Video, Photo, News, Procurement, LocalAct, Legislation, Vacancy

class VideoSerializer(serializers.ModelSerializer):
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

class PhotoSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Photo
        fields = ['id', 'main_image', 'gallery_images', 'date', 'created_at', 'updated_at']

    def validate_main_image(self, value):
        return validate_media(value, 'image')

    def validate_gallery_images(self, value):
        return validate_media_list(value, 'image')

class NewsSerializer(serializers.ModelSerializer):
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
class LocalActSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = LocalAct
        fields = ['id', 'title', 'file_url', 'file_name', 'file_size', 'date', 'created_at', 'updated_at']

    def validate_file_url(self, value):
        return validate_media(value, 'document')

class LegislationSerializer(serializers.ModelSerializer):
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