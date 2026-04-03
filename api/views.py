# api/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from .models import Video, Photo, News, Procurement, Vacancy
from .serializers import *
import time

# ========== ВИДЕО ==========
class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = [AllowAny]

# ========== ФОТО ==========
class PhotoViewSet(viewsets.ModelViewSet):
    queryset = Photo.objects.all()
    serializer_class = PhotoSerializer
    permission_classes = [AllowAny]

# ========== НОВОСТИ ==========
class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all()
    serializer_class = NewsSerializer
    permission_classes = [AllowAny]

# ========== ЗАКУПКИ ==========
class ProcurementViewSet(viewsets.ModelViewSet):
    queryset = Procurement.objects.all()
    serializer_class = ProcurementSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        print("=" * 60)
        print("📥 ПОЛУЧЕНЫ ДАННЫЕ ОТ ФРОНТЕНДА:")
        print(request.data)
        print("=" * 60)
        
        # Создаем копию данных
        data = request.data.copy()
        
        # Добавляем id если его нет
        if 'id' not in data or not data['id']:
            data['id'] = str(int(time.time() * 1000))
            print(f"🆔 Сгенерирован ID: {data['id']}")
        
        # Проверяем обязательные поля
        required_fields = ['number', 'contractNumber', 'supplier', 'type', 'status', 'date', 'amount']
        for field in required_fields:
            if field not in data:
                print(f"❌ Отсутствует поле: {field}")
                return Response(
                    {field: ["This field is required."]}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            print(f"✅ Поле {field}: {data[field]} ({type(data[field])})")
        
        # Преобразуем amount в Decimal если нужно
        if 'amount' in data:
            try:
                data['amount'] = float(data['amount'])
            except:
                pass
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            print("✅ Данные сохранены успешно")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        print("❌ ОШИБКИ ВАЛИДАЦИИ:")
        print(serializer.errors)
        print("=" * 60)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ========== ВАКАНСИИ ==========
class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer
    permission_classes = [AllowAny]

# ========== АДМИН ЛОГИН ==========
@api_view(['POST'])
@csrf_exempt
def admin_login(request):
    """Функция для входа в админ-панель"""
    password = request.data.get('password')
    print(f"Login attempt with password: {password}")
    
    if password == 'admin123':
        return Response({'success': True, 'message': 'Login successful'})
    return Response({'success': False, 'message': 'Invalid password'}, status=status.HTTP_401_UNAUTHORIZED)

# ========== ИМПОРТ ДАННЫХ ==========
@api_view(['POST'])
@csrf_exempt
def import_local_data(request):
    """Функция для импорта данных из localStorage"""
    try:
        data = request.data
        print("Received data keys:", list(data.keys()))
        
        # Импорт новостей
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
        
        # Импорт видео
        if 'videos' in data:
            print(f"Importing {len(data['videos'])} videos")
            for video in data['videos']:
                Video.objects.update_or_create(
                    id=video['id'],
                    defaults={
                        'title': video.get('title', ''),
                        'description': video.get('description', ''),
                        'main_video_url': video.get('main_video_url', ''),
                        'gallery_videos': video.get('gallery_videos', []),
                        'thumbnail': video.get('thumbnail', ''),
                        'date': video.get('date', '2024-01-01'),
                    }
                )
        
        # Импорт фото
        if 'photos' in data:
            print(f"Importing {len(data['photos'])} photos")
            for photo in data['photos']:
                Photo.objects.update_or_create(
                    id=photo['id'],
                    defaults={
                        'title': photo.get('title', ''),
                        'description': photo.get('description', ''),
                        'main_image': photo.get('main_image', ''),
                        'gallery_images': photo.get('gallery_images', []),
                        'date': photo.get('date', '2024-01-01'),
                    }
                )
        
        # Импорт закупок
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
        
        # Импорт вакансий
        if 'vacancies' in data:
            print(f"Importing {len(data['vacancies'])} vacancies")
            for vac in data['vacancies']:
                Vacancy.objects.update_or_create(
                    id=vac['id'],
                    defaults={
                        'title': vac.get('title', ''),
                        'salary_from': vac.get('salaryFrom'),
                        'salary_to': vac.get('salaryTo'),
                        'schedule': vac.get('schedule', ''),
                        'experience': vac.get('experience', ''),
                        'description': vac.get('description', ''),
                        'requirements': vac.get('requirements', []),
                        'responsibilities': vac.get('responsibilities', []),
                        'conditions': vac.get('conditions', []),
                        'status': vac.get('status', 'open'),
                        'published_at': vac.get('publishedAt', '2024-01-01'),
                    }
                )
        
        return Response({'success': True, 'message': 'Data imported successfully'})
    
    except Exception as e:
        print("Error:", str(e))
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)