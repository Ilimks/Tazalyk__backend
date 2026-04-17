from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from django.views.decorators.csrf import csrf_exempt
from .models import Video, Photo, News, Procurement, LocalAct, Legislation
from .serializers import *
import time
import logging

logger = logging.getLogger(__name__)

# ========== ПАГИНАЦИЯ ==========
class VideoPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = 'page_size'
    max_page_size = 100

class PhotoPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = 'page_size'
    max_page_size = 100

class NewsPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProcurementPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class LocalActPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class LegislationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# ========== ВИДЕО ==========
class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all().order_by('-date', '-created_at')
    serializer_class = VideoSerializer
    permission_classes = [AllowAny]
    pagination_class = VideoPagination

# ========== ФОТО ==========
class PhotoViewSet(viewsets.ModelViewSet):
    queryset = Photo.objects.all().order_by('-date', '-created_at')
    serializer_class = PhotoSerializer
    permission_classes = [AllowAny]
    pagination_class = PhotoPagination

# ========== НОВОСТИ ==========
class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all().order_by('-date', '-created_at')
    serializer_class = NewsSerializer
    permission_classes = [AllowAny]
    pagination_class = NewsPagination

# ========== ЗАКУПКИ ==========
class ProcurementViewSet(viewsets.ModelViewSet):
    queryset = Procurement.objects.all().order_by('-date', '-created_at')
    serializer_class = ProcurementSerializer
    permission_classes = [AllowAny]
    pagination_class = ProcurementPagination
    
    def create(self, request, *args, **kwargs):
        print("=" * 60)
        print("📥 ПОЛУЧЕНЫ ДАННЫЕ ОТ ФРОНТЕНДА:")
        print(request.data)
        print("=" * 60)
        
        data = request.data.copy()
        
        if 'id' not in data or not data['id']:
            data['id'] = str(int(time.time() * 1000))
            print(f"🆔 Сгенерирован ID: {data['id']}")
        
        if 'number' in data:
            del data['number']
            print("🔢 Поле number удалено из запроса (будет сгенерировано автоматически)")
        
        required_fields = ['contractNumber', 'supplier', 'type', 'status', 'date', 'amount']
        for field in required_fields:
            if field not in data:
                print(f"❌ Отсутствует поле: {field}")
                return Response(
                    {field: ["This field is required."]}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            print(f"✅ Поле {field}: {data[field]} ({type(data[field])})")
        
        if 'amount' in data:
            try:
                data['amount'] = float(data['amount'])
            except:
                pass
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            print(f"✅ Данные сохранены успешно! Номер закупки: {serializer.data.get('number')}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        print("❌ ОШИБКИ ВАЛИДАЦИИ:")
        print(serializer.errors)
        print("=" * 60)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ========== ЛОКАЛЬНЫЕ АКТЫ ==========
class LocalActViewSet(viewsets.ModelViewSet):
    queryset = LocalAct.objects.all().order_by('-date', '-created_at')
    serializer_class = LocalActSerializer
    permission_classes = [AllowAny]
    pagination_class = LocalActPagination

# ========== ЗАКОНОДАТЕЛЬСТВО ==========
class LegislationViewSet(viewsets.ModelViewSet):
    queryset = Legislation.objects.all().order_by('-date', '-created_at')
    serializer_class = LegislationSerializer
    permission_classes = [AllowAny]
    pagination_class = LegislationPagination

# ========== АДМИН ЛОГИН ==========
@csrf_exempt
@api_view(['POST'])
def admin_login(request):
    """Функция для входа в админ-панель"""
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    ip = request.META.get('REMOTE_ADDR')
    
    logger.warning(f'Login attempt from IP: {ip}, username: {username}')
    
    # Проверка пользователей
    if username == 'admin' and password == 'admin123':
        logger.info(f'Successful login for user: {username} from IP: {ip}')
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': '1',
                'username': 'admin',
                'role': 'admin',
                'permissions': ['*']
            }
        })
    elif username == 'content_manager' and password == 'content123':
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': '2',
                'username': 'content_manager',
                'role': 'content_manager',
                'permissions': [
                    'view_videos', 'create_videos', 'edit_videos', 'delete_videos',
                    'view_photos', 'create_photos', 'edit_photos', 'delete_photos',
                    'view_news', 'create_news', 'edit_news', 'delete_news'
                ]
            }
        })
    elif username == 'procurement_manager' and password == 'procurement123':
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': '3',
                'username': 'procurement_manager',
                'role': 'procurement_manager',
                'permissions': [
                    'view_procurements', 'create_procurements', 'edit_procurements', 'delete_procurements'
                ]
            }
        })
    elif username == 'legal_manager' and password == 'legal123':
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': '5',
                'username': 'legal_manager',
                'role': 'legal_manager',
                'permissions': [
                    'view_local_acts', 'create_local_acts', 'edit_local_acts', 'delete_local_acts',
                    'view_legislation', 'create_legislation', 'edit_legislation', 'delete_legislation'
                ]
            }
        })
    elif username == 'viewer' and password == 'viewer123':
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': '4',
                'username': 'viewer',
                'role': 'viewer',
                'permissions': [
                    'view_videos', 'view_photos', 'view_news', 'view_procurements',
                    'view_local_acts', 'view_legislation'
                ]
            }
        })
    
    logger.warning(f'Failed login attempt for user: {username} from IP: {ip}')
    return Response(
        {'success': False, 'message': 'Неверный логин или пароль'},
        status=status.HTTP_401_UNAUTHORIZED
    )

# ========== ИМПОРТ ДАННЫХ ==========
@csrf_exempt
@api_view(['POST'])
def import_local_data(request):
    """Функция для импорта данных из localStorage"""
    try:
        data = request.data
        print("Received data keys:", list(data.keys()))
        
        if 'news' in data:
            print(f"Importing {len(data['news'])} news items")
            for news_item in data['news']:
                News.objects.update_or_create(
                    id=news_item['id'],
                    defaults={
                        'title': news_item.get('title', ''),
                        'description': news_item.get('description', ''),
                        'image': news_item.get('image', ''),
                        'date': news_item.get('date', '2024-01-01'),
                    }
                )
        
        if 'videos' in data:
            print(f"Importing {len(data['videos'])} videos")
            for video in data['videos']:
                Video.objects.update_or_create(
                    id=video['id'],
                    defaults={
                        'main_video_url': video.get('main_video_url', ''),
                        'gallery_videos': video.get('gallery_videos', []),
                        'thumbnail': video.get('thumbnail', ''),
                        'date': video.get('date', '2024-01-01'),
                    }
                )
        
        if 'photos' in data:
            print(f"Importing {len(data['photos'])} photos")
            for photo in data['photos']:
                Photo.objects.update_or_create(
                    id=photo['id'],
                    defaults={
                        'main_image': photo.get('main_image', ''),
                        'gallery_images': photo.get('gallery_images', []),
                        'date': photo.get('date', '2024-01-01'),
                    }
                )
        
        if 'procurements' in data:
            print(f"Importing {len(data['procurements'])} procurements")
            for proc in data['procurements']:
                Procurement.objects.update_or_create(
                    id=proc['id'],
                    defaults={
                        'number': proc.get('number', ''),
                        'contractNumber': proc.get('contractNumber', proc.get('contract_number', '')),
                        'supplier': proc.get('supplier', ''),
                        'type': proc.get('type', 'goods'),
                        'method': proc.get('method', 'direct'),
                        'status': proc.get('status', 'active'),
                        'date': proc.get('date', '2024-01-01'),
                        'amount': proc.get('amount', 0),
                    }
                )
        
        if 'local_acts' in data:
            print(f"Importing {len(data['local_acts'])} local acts")
            for act in data['local_acts']:
                LocalAct.objects.update_or_create(
                    id=act['id'],
                    defaults={
                        'title': act.get('title', ''),
                        'file_url': act.get('file_url', ''),
                        'file_name': act.get('file_name', ''),
                        'file_size': act.get('file_size', 0),
                        'date': act.get('date', '2024-01-01'),
                    }
                )
        
        if 'legislation' in data:
            print(f"Importing {len(data['legislation'])} legislation items")
            for leg in data['legislation']:
                Legislation.objects.update_or_create(
                    id=leg['id'],
                    defaults={
                        'title': leg.get('title', ''),
                        'file_url': leg.get('file_url', ''),
                        'file_name': leg.get('file_name', ''),
                        'file_size': leg.get('file_size', 0),
                        'date': leg.get('date', '2024-01-01'),
                    }
                )
        
        return Response({'success': True, 'message': 'Data imported successfully'})
    
    except Exception as e:
        print("Error:", str(e))
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========== HEALTH CHECK ==========
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok', 'message': 'Server is running'})