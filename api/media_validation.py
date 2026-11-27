import base64
import binascii
import io
import re
import zipfile

from rest_framework import serializers

MB = 1024 * 1024
DATA_URL_RE = re.compile(r'^data:([\w.+-]+/[\w.+-]+)(?:;[\w=.-]+)*;base64,')
HEADER_BASE64_CHARS = 32
MAX_GALLERY_ITEMS = 50


def _is_iso_media(head):
    return head[4:8] in (b'ftyp', b'moov', b'mdat', b'free', b'wide')


def _is_office(head):
    return head[:4] == b'\xd0\xcf\x11\xe0' or head[:4] == b'PK\x03\x04'


IMAGE_TYPES = {
    'image/jpeg': lambda head: head[:3] == b'\xff\xd8\xff',
    'image/png': lambda head: head[:8] == b'\x89PNG\r\n\x1a\n',
    'image/gif': lambda head: head[:4] == b'GIF8',
    'image/webp': lambda head: head[:4] == b'RIFF' and head[8:12] == b'WEBP',
}
VIDEO_TYPES = {
    'video/mp4': _is_iso_media,
    'video/quicktime': _is_iso_media,
    'video/webm': lambda head: head[:4] == b'\x1a\x45\xdf\xa3',
    'video/ogg': lambda head: head[:4] == b'OggS',
}
DOCUMENT_TYPES = {
    'application/pdf': lambda head: head[:4] == b'%PDF',
    'application/msword': _is_office,
    'application/vnd.ms-excel': _is_office,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': _is_office,
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': _is_office,
    'application/octet-stream': _is_office,
    'text/plain': None,
}

KINDS = {
    'image': (IMAGE_TYPES, 20 * MB),
    'video': (VIDEO_TYPES, 100 * MB),
    'document': (DOCUMENT_TYPES, 50 * MB),
}


RESUME_MAX_BYTES = 5 * MB
DOCX_MAX_UNPACKED_BYTES = 50 * MB
DOCX_MAX_ENTRIES = 2000
RESUME_TYPES = (
    (DOCUMENT_TYPES['application/pdf'], 'pdf', 'application/pdf'),
    (
        lambda head: head[:4] == b'PK\x03\x04',
        'docx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ),
    (IMAGE_TYPES['image/jpeg'], 'jpg', 'image/jpeg'),
    (IMAGE_TYPES['image/png'], 'png', 'image/png'),
)


def detect_resume_type(content):
    for signature_ok, extension, content_type in RESUME_TYPES:
        if signature_ok(content[:16]):
            return extension, content_type
    return None


EXTERNAL_RELATION_RE = re.compile(rb'<Relationship\b[^>]*TargetMode="External"[^>]*>')
RELATION_TYPE_RE = re.compile(rb'Type="[^"]*/([A-Za-z]+)"')


def is_safe_docx(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > DOCX_MAX_ENTRIES or sum(item.file_size for item in entries) > DOCX_MAX_UNPACKED_BYTES:
                return False

            names = {item.filename.lower() for item in entries}
            if not {'[content_types].xml', 'word/document.xml'} <= names:
                return False
            if any(name.endswith('vbaproject.bin') or '/embeddings/oleobject' in name for name in names):
                return False

            for item in entries:
                if not item.filename.lower().endswith('.rels'):
                    continue
                for relation in EXTERNAL_RELATION_RE.findall(archive.read(item)):
                    kind = RELATION_TYPE_RE.search(relation)
                    if not kind or kind.group(1) != b'hyperlink':
                        return False
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError, EOFError, ValueError):
        return False
    return True


def validate_media(value, kind):
    if not value:
        return value
    if not isinstance(value, str):
        raise serializers.ValidationError('Ожидается строка.')

    if not value.startswith('data:'):
        if value.startswith(('http://', 'https://')) or (value.startswith('/') and not value.startswith('//')):
            return value
        raise serializers.ValidationError('Допустима только ссылка http(s) или файл.')

    types, max_bytes = KINDS[kind]
    match = DATA_URL_RE.match(value[:300])
    if not match or match.group(1) not in types:
        raise serializers.ValidationError('Этот тип файла не поддерживается.')

    payload_start = match.end()
    if len(value) - payload_start > max_bytes * 4 // 3 + 4:
        raise serializers.ValidationError(f'Файл больше {max_bytes // MB} МБ.')

    signature_ok = types[match.group(1)]
    if signature_ok is not None:
        try:
            head = base64.b64decode(value[payload_start:payload_start + HEADER_BASE64_CHARS], validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError('Повреждённые данные файла.')
        if not signature_ok(head):
            raise serializers.ValidationError('Содержимое файла не совпадает с его типом.')
    return value


def validate_media_list(values, kind):
    if not isinstance(values, list):
        raise serializers.ValidationError('Ожидается список.')
    if len(values) > MAX_GALLERY_ITEMS:
        raise serializers.ValidationError(f'Не больше {MAX_GALLERY_ITEMS} файлов в галерее.')
    return [validate_media(item, kind) for item in values]
