from rest_framework import serializers
from .models import Video, Photo, News, Procurement, LocalAct, Legislation

class VideoSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Video
        fields = ['id', 'main_video_url', 'gallery_videos', 'thumbnail', 'date', 'created_at', 'updated_at']

class PhotoSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Photo
        fields = ['id', 'main_image', 'gallery_images', 'date', 'created_at', 'updated_at']

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

class LegislationSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Legislation
        fields = ['id', 'title', 'file_url', 'file_name', 'file_size', 'date', 'created_at', 'updated_at']