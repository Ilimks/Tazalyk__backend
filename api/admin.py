from django.contrib import admin
from .models import Video, Photo, News, Procurement, LocalAct, Legislation

class BaseDocumentAdmin(admin.ModelAdmin):
    """Базовый класс для документов"""
    list_display = ['title', 'file_name', 'file_size', 'date', 'created_at']
    list_filter = ['date', 'created_at']
    search_fields = ['title', 'file_name']
    ordering = ['-date', '-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['date', 'created_at']
    list_filter = ['date', 'created_at']
    ordering = ['-date', '-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ['date', 'created_at']
    list_filter = ['date', 'created_at']
    ordering = ['-date', '-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'created_at']
    list_filter = ['date', 'created_at']
    search_fields = ['title', 'description']
    ordering = ['-date', '-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(Procurement)
class ProcurementAdmin(admin.ModelAdmin):
    list_display = ['number', 'contractNumber', 'supplier', 'type', 'method', 'status', 'date', 'amount']
    list_filter = ['type', 'method', 'status', 'date']
    search_fields = ['number', 'contractNumber', 'supplier']
    ordering = ['-date', '-created_at']
    readonly_fields = ['id', 'number', 'created_at', 'updated_at']

@admin.register(LocalAct)
class LocalActAdmin(BaseDocumentAdmin):
    pass

@admin.register(Legislation)
class LegislationAdmin(BaseDocumentAdmin):
    pass