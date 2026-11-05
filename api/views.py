from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission, SAFE_METHODS
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .models import Video, Photo, News, Procurement, LocalAct, Legislation, Vacancy
from .security_events import log_login_success, log_login_throttled
from rest_framework import filters
from .serializers import *
import time
import logging

logger = logging.getLogger(__name__)

# ========== ПРАВА ДОСТУПА ==========
# Какая группа пользователей может менять раздел (группы создаёт create_users.py)
SECTION_GROUPS = {
    'videos': 'content_managers',
    'photos': 'content_managers',
    'news': 'content_managers',
    'procurements': 'procurement_managers',
    'local_acts': 'legal_managers',
    'legislation': 'legal_managers',
    # отдел кадров (группу создаёт миграция 0016, сотрудника — manage.py create_hr_user)
    'vacancies': 'hr_managers',
}

def can_edit_section(user, section):
    """Суперпользователь или сотрудник из группы раздела"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=SECTION_GROUPS[section]).exists()

class SectionPermission(BasePermission):
    """Читать могут все (сайт), менять — суперпользователь или группа раздела"""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return can_edit_section(request.user, view.section)

# ========== ПАГИНАЦИЯ ==========
class MediaPagination(PageNumberPagination):
    """Записи с файлами в base64 тяжёлые: один запрос на 100 штук весил сотни мегабайт.
    Посетителям — до 20 записей на страницу, сотрудникам в админке — как раньше."""
    page_size_query_param = 'page_size'
    max_page_size = 100
    public_max_page_size = 20

    def get_page_size(self, request):
        size = super().get_page_size(request)
        if request.user and request.user.is_authenticated:
            return size
        return min(size, self.public_max_page_size)

class VideoPagination(MediaPagination):
    page_size = 8

class PhotoPagination(MediaPagination):
    page_size = 8

class NewsPagination(MediaPagination):
    page_size = 12

class ProcurementPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class LocalActPagination(MediaPagination):
    page_size = 10

class LegislationPagination(MediaPagination):
    page_size = 10

class VacancyPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# ========== ВИДЕО ==========
class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all().order_by('-date', '-created_at')
    serializer_class = VideoSerializer
    permission_classes = [SectionPermission]
    section = 'videos'
    pagination_class = VideoPagination

# ========== ФОТО ==========
class PhotoViewSet(viewsets.ModelViewSet):
    queryset = Photo.objects.all().order_by('-date', '-created_at')
    serializer_class = PhotoSerializer
    permission_classes = [SectionPermission]
    section = 'photos'
    pagination_class = PhotoPagination

# ========== НОВОСТИ ==========
class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all().order_by('-date', '-created_at')   # исправлено
    serializer_class = NewsSerializer
    permission_classes = [SectionPermission]
    section = 'news'
    pagination_class = NewsPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title_ru', 'title_ky', 'description_ru', 'description_ky']
    ordering_fields = ['date', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        year = self.request.query_params.get('year')
        if year and year.isdigit():
            queryset = queryset.filter(date__year=year)
        return queryset

# ========== ЗАКУПКИ ==========
class ProcurementViewSet(viewsets.ModelViewSet):
    queryset = Procurement.objects.all().order_by('-date', '-created_at')
    serializer_class = ProcurementSerializer
    permission_classes = [SectionPermission]
    section = 'procurements'
    pagination_class = ProcurementPagination
    
    def create(self, request, *args, **kwargs):
        # тело запроса в лог не пишем: там данные поставщиков и суммы договоров
        data = request.data.copy()

        if 'id' not in data or not data['id']:
            data['id'] = str(int(time.time() * 1000))

        # номер закупки сервер присваивает сам
        data.pop('number', None)

        required_fields = ['contractNumber', 'supplier', 'type', 'status', 'date', 'amount']
        for field in required_fields:
            if field not in data:
                return Response(
                    {field: ["This field is required."]},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # сумму не переводим во float — DecimalField сам разбирает строку без потери копеек
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            logger.info('Procurement created: number=%s by user=%s', serializer.data.get('number'), request.user.pk)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ========== ЛОКАЛЬНЫЕ АКТЫ ==========
class LocalActViewSet(viewsets.ModelViewSet):
    queryset = LocalAct.objects.all().order_by('-date', '-created_at')
    serializer_class = LocalActSerializer
    permission_classes = [SectionPermission]
    section = 'local_acts'
    pagination_class = LocalActPagination

# ========== ЗАКОНОДАТЕЛЬСТВО ==========
class LegislationViewSet(viewsets.ModelViewSet):
    queryset = Legislation.objects.all().order_by('-date', '-created_at')
    serializer_class = LegislationSerializer
    permission_classes = [SectionPermission]
    section = 'legislation'
    pagination_class = LegislationPagination

# ========== ВАКАНСИИ ==========
class VacancyViewSet(viewsets.ModelViewSet):
    serializer_class = VacancySerializer
    permission_classes = [SectionPermission]
    section = 'vacancies'
    pagination_class = VacancyPagination

    def get_queryset(self):
        queryset = Vacancy.objects.all().order_by('-created_at')
        params = self.request.query_params
        # неактивные вакансии видит только отдел кадров: в списке админки (?all=1) и при редактировании
        manager_view = can_edit_section(self.request.user, self.section) and (
            self.action != 'list' or params.get('all') == '1'
        )
        if not manager_view:
            return queryset.filter(is_active=True)
        # фильтр «активные / неактивные» в админке
        is_active = params.get('is_active')
        if self.action == 'list' and is_active in ('1', '0'):
            queryset = queryset.filter(is_active=is_active == '1')
        return queryset

# ========== ВХОД В АДМИНКУ ==========
# Стандартный вход simplejwt с ограничением числа попыток: без него пароли можно было перебирать.
# Лимиты — REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login'/'token_refresh'] в settings.py
class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            log_login_success(request, request.data.get('username'))
        return response

    def throttled(self, request, wait):
        log_login_throttled(request)
        super().throttled(request, wait)


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_refresh'

# Импорт из localStorage (/api/import-data/) удалён: любой вошедший сотрудник мог им
# перезаписать все разделы в обход проверки прав и валидации.

# ========== ТЕКУЩИЙ ПОЛЬЗОВАТЕЛЬ ==========
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Роль сотрудника для админки: суперпользователь и группы (раньше админка угадывала роль по логину)"""
    user = request.user
    return Response({
        'username': user.username,
        'is_superuser': user.is_superuser,
        'groups': list(user.groups.values_list('name', flat=True)),
    })

# ========== HEALTH CHECK ==========
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok', 'message': 'Server is running'})