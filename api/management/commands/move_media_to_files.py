"""Переносит видео, фото, новости и документы из базы в файлы. Запускается после обновления сервера."""
from django.core.management.base import BaseCommand
from rest_framework import serializers

from api.media_files import make_faststart
from api.serializers import (
    LegislationSerializer,
    LocalActSerializer,
    NewsSerializer,
    PhotoSerializer,
    VideoSerializer,
)

SERIALIZERS = (VideoSerializer, PhotoSerializer, NewsSerializer, LocalActSerializer, LegislationSerializer)


class Command(BaseCommand):
    help = 'Переносит файлы из базы в MEDIA_ROOT и готовит MP4 к быстрому старту. Запускать можно повторно.'

    def handle(self, *args, **options):
        moved = failed = prepared = 0
        for serializer in SERIALIZERS:
            model = serializer.Meta.model
            fields = (*serializer.file_fields, *serializer.file_list_fields)
            # записи тяжёлые, поэтому читаем их по одной
            for pk in model.objects.order_by().values_list('pk', flat=True):
                record = model.objects.get(pk=pk)
                current = {field: getattr(record, field) for field in fields}
                try:
                    stored = serializer.store_files(current)
                except serializers.ValidationError as error:
                    failed += 1
                    self.stderr.write(f'{model.__name__} {pk}: запись не перенесена: {error.detail[0]}')
                    continue

                if stored != current:
                    # update: дата изменения записи остаётся прежней
                    model.objects.filter(pk=pk).update(**stored)
                    moved += 1

                # записи, перенесённые раньше, тоже могут быть с оглавлением по всему файлу
                prepared += sum(make_faststart(name) for name in serializer.stored_files(model.objects.get(pk=pk)))

        self.stdout.write(f'Перенесено записей: {moved}, с ошибкой: {failed}, подготовлено видео: {prepared}')
