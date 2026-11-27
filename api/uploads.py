import uuid

from django.core.files.storage import default_storage
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .media_files import EXTENSIONS, make_faststart, public_url
from .media_validation import KINDS, MB
from .views import can_edit_section

SECTIONS = {
    'videos': ('videos', ('video', 'image')),
    'photos': ('photos', ('image',)),
    'news': ('news', ('image',)),
    'local_acts': ('documents', ('document',)),
    'legislation': ('documents', ('document',)),
}
HEAD_BYTES = 16


def upload_limits():
    return {
        kind: {'maxBytes': max_bytes, 'types': sorted(types)}
        for kind, (types, max_bytes) in KINDS.items()
    }


class UploadSerializer(serializers.Serializer):
    section = serializers.ChoiceField(choices=sorted(SECTIONS))
    kind = serializers.ChoiceField(choices=sorted(KINDS))
    file = serializers.FileField(allow_empty_file=True)

    def validate(self, data):
        folder, kinds = SECTIONS[data['section']]
        if data['kind'] not in kinds:
            raise serializers.ValidationError({'kind': 'В этот раздел такой файл не загружается.'})

        types, max_bytes = KINDS[data['kind']]
        upload = data['file']
        if upload.size == 0:
            raise serializers.ValidationError({'file': 'Файл пустой.'})
        if upload.size > max_bytes:
            raise serializers.ValidationError({'file': f'Файл больше {max_bytes // MB} МБ.'})
        if upload.content_type not in types:
            raise serializers.ValidationError({'file': 'Этот тип файла не поддерживается.'})

        signature_ok = types[upload.content_type]
        head = upload.read(HEAD_BYTES)
        upload.seek(0)
        if signature_ok is not None and not signature_ok(head):
            raise serializers.ValidationError({'file': 'Содержимое файла не совпадает с его типом.'})

        data['folder'] = folder
        data['extension'] = EXTENSIONS[upload.content_type]
        return data


class UploadView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(upload_limits())

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not can_edit_section(request.user, data['section']):
            return Response({'detail': 'Недостаточно прав для этого раздела.'}, status=status.HTTP_403_FORBIDDEN)

        name = default_storage.save(f"{data['folder']}/{uuid.uuid4().hex}.{data['extension']}", data['file'])
        if data['kind'] == 'video':
            make_faststart(name)
        url = public_url(default_storage.url(name), request)
        return Response({'url': url, 'size': data['file'].size}, status=status.HTTP_201_CREATED)
