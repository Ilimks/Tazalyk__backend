"""Видео, фото и документы лежат файлами в MEDIA_ROOT, в базе — только путь /media/<папка>/<имя>.

Пока файлы хранились внутри записи, они попадали в каждый ответ API: список из 4 карточек видео
весил 109 МБ. Сайт не мог показать ни одного превью, пока не дочитает ответ, а десяток таких
запросов занимал всю память сервера.
"""
import base64
import binascii
import logging
import os
import re
import struct
import subprocess
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponse
from django.views.static import serve
from rest_framework import serializers

from .media_validation import DATA_URL_RE

logger = logging.getLogger(__name__)

FOLDERS = ('videos', 'photos', 'news', 'documents')
# расширение выбираем по типу, прошедшему проверку: имя от пользователя в путь не попадает
EXTENSIONS = {
    'video/mp4': 'mp4',
    'video/quicktime': 'mov',
    'video/webm': 'webm',
    'video/ogg': 'ogv',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.ms-excel': 'xls',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/octet-stream': 'bin',
    'text/plain': 'txt',
}
# только имена, которые выдаём сами: из значения нельзя собрать путь к чужому файлу
STORED_NAME_RE = re.compile(rf'^(?:{"|".join(FOLDERS)})/[0-9a-f]{{32}}\.[a-z0-9]+$')

STREAMABLE_EXTENSIONS = ('.mp4', '.mov')
REMUX_TIMEOUT_SECONDS = 120

# имя файла уникально и содержимое под ним не меняется
CACHE_SECONDS = 365 * 24 * 60 * 60
RANGE_RE = re.compile(r'^bytes=(\d*)-(\d*)$')


def _stored_name(value):
    """Имя файла внутри MEDIA_ROOT по пути или ссылке; None — это не наш файл"""
    path = urlsplit(value or '').path
    if not path.startswith(settings.MEDIA_URL):
        return None
    name = path[len(settings.MEDIA_URL):]
    return name if STORED_NAME_RE.match(name) else None


def _needs_faststart(path):
    """Оглавление MP4 разбито по файлу (moof) или лежит за данными.

    Такой файл браузер просматривает целиком ещё до первого кадра: ролик на 25 МБ давал 141 запрос
    и 10 секунд ожидания даже на локальной машине, а по сети это намного дольше.
    """
    size = os.path.getsize(path)
    moov_seen = False
    position = 0
    with open(path, 'rb') as file:
        while position + 8 <= size:
            file.seek(position)
            header = file.read(16)
            length, kind = struct.unpack('>I4s', header[:8])
            if length == 1 and len(header) == 16:
                length = struct.unpack('>Q', header[8:])[0]
            elif length == 0:
                length = size - position
            if length < 8:
                return False

            if kind == b'moof':
                return True
            if kind == b'mdat':
                return not moov_seen
            if kind == b'moov':
                moov_seen = True
            position += length
    return False


def make_faststart(name):
    """Перекладывает MP4 без перекодирования: оглавление в начало, качество не меняется.

    Если не вышло, остаётся исходный файл: он просто дольше стартует.
    """
    path = default_storage.path(name)
    extension = os.path.splitext(path)[1]
    if extension not in STREAMABLE_EXTENSIONS or not _needs_faststart(path):
        return False

    temporary = f'{path}.tmp{extension}'
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        subprocess.run(
            [
                get_ffmpeg_exe(), '-nostdin', '-v', 'error', '-y',
                # файл от сотрудника: читаем только как MP4 и только с диска, ссылки внутри не открываем
                '-protocol_whitelist', 'file', '-f', 'mov', '-i', path,
                '-c', 'copy', '-movflags', '+faststart', temporary,
            ],
            check=True,
            capture_output=True,
            timeout=REMUX_TIMEOUT_SECONDS,
            # секреты сервера программе не нужны
            env={},
        )
        os.replace(temporary, path)
        return True
    except (ImportError, OSError, subprocess.SubprocessError) as error:
        logger.warning('Не удалось подготовить видео %s: %s', name, error)
        return False
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def store_file(value, folder):
    """data URL становится файлом. Ссылка на наш файл — путём без домена, чужая ссылка не меняется"""
    if value.startswith('data:'):
        match = DATA_URL_RE.match(value[:300])
        extension = EXTENSIONS.get(match.group(1)) if match else None
        if extension is None:
            raise serializers.ValidationError('Этот тип файла не поддерживается.')
        try:
            content = base64.b64decode(value[match.end():], validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError('Повреждённые данные файла.')
        name = default_storage.save(f'{folder}/{uuid.uuid4().hex}.{extension}', ContentFile(content))
        make_faststart(name)
        return default_storage.url(name)

    name = _stored_name(value)
    return default_storage.url(name) if name else value


def stored_names(values):
    return {name for name in map(_stored_name, values) if name}


def delete_files(names):
    for name in names:
        default_storage.delete(name)


def public_url(value, request):
    """Полный адрес нашего файла для ответа API. Записи, которые ещё не перенесены, отдаются как есть"""
    if not value or not _stored_name(value):
        return value
    # на сервере за прокси адрес задаётся явно, чтобы не получить http:// на https-сайте
    base = getattr(settings, 'PUBLIC_MEDIA_BASE_URL', '')
    if base:
        return f'{base.rstrip("/")}{value}'
    return request.build_absolute_uri(value) if request else value


class StoredFilesMixin:
    """Сериализатор, поля которого хранят файлы на диске.

    В потомке: file_folder — папка, file_fields — поля с одним файлом, file_list_fields — со списком.
    """

    file_folder = ''
    file_fields = ()
    file_list_fields = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        for field in self.file_fields:
            data[field] = public_url(data[field], request)
        for field in self.file_list_fields:
            data[field] = [public_url(item, request) for item in data[field]]
        return data

    def create(self, validated_data):
        return super().create(self.store_files(validated_data))

    def update(self, instance, validated_data):
        previous_files = self.stored_files(instance)
        instance = super().update(instance, self.store_files(validated_data))
        delete_files(previous_files - self.stored_files(instance))
        return instance

    @classmethod
    def store_files(cls, data):
        """Копия данных записи, где содержимое файлов заменено путями"""
        stored = dict(data)
        for field in cls.file_fields:
            if stored.get(field):
                stored[field] = store_file(stored[field], cls.file_folder)
        for field in cls.file_list_fields:
            if field in stored:
                stored[field] = [store_file(item, cls.file_folder) for item in stored[field] if item]
        return stored

    @classmethod
    def stored_files(cls, instance):
        """Имена файлов, которыми пользуется запись"""
        values = [getattr(instance, field) for field in cls.file_fields]
        for field in cls.file_list_fields:
            values.extend(getattr(instance, field) or [])
        return stored_names(values)


class DeletesStoredFilesMixin:
    """Вьюсет: вместе с записью удаляются её файлы"""

    def perform_destroy(self, instance):
        files = self.get_serializer_class().stored_files(instance)
        instance.delete()
        delete_files(files)


class _FilePart:
    """Кусок файла для ответа на запрос Range"""

    def __init__(self, file, start, length):
        file.seek(start)
        self.file = file
        self.remaining = length

    def read(self, size=-1):
        limit = self.remaining if size < 0 else min(size, self.remaining)
        chunk = self.file.read(limit)
        self.remaining -= len(chunk)
        return chunk

    def close(self):
        self.file.close()


def _parse_range(header, size):
    """Первый и последний байт запроса. None — заголовка нет, ValueError — запрос вне файла"""
    match = RANGE_RE.match(header or '')
    if not match or not any(match.groups()):
        return None

    first, last = match.groups()
    if not first:
        # bytes=-500: последние 500 байт
        if int(last) == 0:
            raise ValueError('пустой диапазон')
        return max(size - int(last), 0), size - 1
    start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise ValueError('запрос вне файла')
    return start, end


def serve_media(request, path):
    """Запасной вариант для nginx. Как serve из Django, но с Range: без него Safari не запускает видео"""
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    if response.status_code != 200:
        return response

    cache_control = f'public, max-age={CACHE_SECONDS}, immutable'
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = cache_control

    size = int(response['Content-Length'])
    try:
        requested = _parse_range(request.headers.get('Range'), size)
    except ValueError:
        response.close()
        return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
    if requested is None:
        return response

    start, end = requested
    length = end - start + 1
    partial = FileResponse(
        _FilePart(response.file_to_stream, start, length),
        status=206,
        content_type=response['Content-Type'],
    )
    partial['Content-Length'] = length
    partial['Content-Range'] = f'bytes {start}-{end}/{size}'
    partial['Accept-Ranges'] = 'bytes'
    partial['Cache-Control'] = cache_control
    partial['Last-Modified'] = response['Last-Modified']
    return partial
