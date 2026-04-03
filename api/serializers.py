# api/serializers.py
from rest_framework import serializers
from .models import Video, Photo, News, Procurement, Vacancy

class VideoSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Video
        fields = ['id', 'title', 'description', 'main_video_url', 'gallery_videos', 'thumbnail', 'date', 'created_at', 'updated_at']

class PhotoSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Photo
        fields = ['id', 'title', 'description', 'main_image', 'gallery_images', 'date', 'created_at', 'updated_at']

class NewsSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = News
        fields = ['id', 'title', 'description', 'image', 'date', 'created_at', 'updated_at']

class ProcurementSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Procurement
        fields = ['id', 'number', 'contractNumber', 'supplier', 'type', 'method', 'status', 'date', 'amount', 'created_at', 'updated_at']

class VacancySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Vacancy
        fields = '__all__'