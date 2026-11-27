import os
import time

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from api.media_files import FOLDERS, stored_names
from api.models import LocalAct, Legislation, News, Photo, Video
from api.serializers import LegislationSerializer, LocalActSerializer, NewsSerializer, PhotoSerializer, VideoSerializer

OWNERS = (
    (Video, VideoSerializer),
    (Photo, PhotoSerializer),
    (News, NewsSerializer),
    (LocalAct, LocalActSerializer),
    (Legislation, LegislationSerializer),
)


def referenced_names():
    names = set()
    for model, serializer in OWNERS:
        for instance in model.objects.all().iterator():
            names |= serializer.stored_files(instance)
    return names


class Command(BaseCommand):
    help = 'Удаляет загруженные файлы, которые не попали ни в одну запись'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, hours, dry_run, **options):
        keep = referenced_names()
        deadline = time.time() - hours * 3600
        removed = 0
        for folder in FOLDERS:
            if not default_storage.exists(folder):
                continue
            _, files = default_storage.listdir(folder)
            for file in files:
                name = f'{folder}/{file}'
                if name in keep or not stored_names([f'{settings.MEDIA_URL}{name}']):
                    continue
                if os.path.getmtime(default_storage.path(name)) > deadline:
                    continue
                removed += 1
                if not dry_run:
                    default_storage.delete(name)
        self.stdout.write(f'{"Нашлось бы" if dry_run else "Удалено"} файлов без записи: {removed}')
