import hmac

from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission, SAFE_METHODS
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .authentication import REFRESH_COOKIE, delete_auth_cookies, require_admin_origin, set_auth_cookies
from .exports import applications_export_response
from .list_search import ListSearchFilter
from .media_files import DeletesStoredFilesMixin
from .models import (
    Complaint, ComplaintPhoto, Video, Photo, News, Procurement, LocalAct, Legislation, Vacancy, VacancyApplication,
    SiteSettings,
)
from .security_events import log_login_success, log_login_throttled
from rest_framework import filters
from .serializers import *
import time
import logging

logger = logging.getLogger(__name__)

SECTION_GROUPS = {
    'videos': 'content_managers',
    'photos': 'content_managers',
    'news': 'content_managers',
    'procurements': 'procurement_managers',
    'local_acts': 'legal_managers',
    'legislation': 'legal_managers',
    'vacancies': 'hr_managers',
    'complaints': 'complaints_managers',
    'site_settings': 'content_managers',
}

def can_edit_section(user, section):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=SECTION_GROUPS[section]).exists()

class SectionPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return can_edit_section(request.user, view.section)

class MediaPagination(PageNumberPagination):
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

class VideoViewSet(DeletesStoredFilesMixin, viewsets.ModelViewSet):
    queryset = Video.objects.all().order_by('-date', '-created_at')
    serializer_class = VideoSerializer
    permission_classes = [SectionPermission]
    section = 'videos'
    pagination_class = VideoPagination

class PhotoViewSet(DeletesStoredFilesMixin, viewsets.ModelViewSet):
    queryset = Photo.objects.all().order_by('-date', '-created_at')
    serializer_class = PhotoSerializer
    permission_classes = [SectionPermission]
    section = 'photos'
    pagination_class = PhotoPagination

class NewsViewSet(DeletesStoredFilesMixin, viewsets.ModelViewSet):
    queryset = News.objects.all().order_by('-date', '-created_at')
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

class ProcurementViewSet(viewsets.ModelViewSet):
    queryset = Procurement.objects.all().order_by('-date', '-created_at')
    serializer_class = ProcurementSerializer
    permission_classes = [SectionPermission]
    section = 'procurements'
    pagination_class = ProcurementPagination
    filter_backends = [ListSearchFilter]
    search_text = ['number', 'contractNumber', 'supplier']
    
    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        if 'id' not in data or not data['id']:
            data['id'] = str(int(time.time() * 1000))

        data.pop('number', None)

        required_fields = ['contractNumber', 'supplier', 'type', 'status', 'date', 'amount']
        for field in required_fields:
            if field not in data:
                return Response(
                    {field: ["This field is required."]},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            logger.info('Procurement created: number=%s by user=%s', serializer.data.get('number'), request.user.pk)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LocalActViewSet(DeletesStoredFilesMixin, viewsets.ModelViewSet):
    queryset = LocalAct.objects.all().order_by('-date', '-created_at')
    serializer_class = LocalActSerializer
    permission_classes = [SectionPermission]
    section = 'local_acts'
    pagination_class = LocalActPagination
    filter_backends = [ListSearchFilter]
    search_text = ['title', 'file_name']

class LegislationViewSet(DeletesStoredFilesMixin, viewsets.ModelViewSet):
    queryset = Legislation.objects.all().order_by('-date', '-created_at')
    serializer_class = LegislationSerializer
    permission_classes = [SectionPermission]
    section = 'legislation'
    pagination_class = LegislationPagination
    filter_backends = [ListSearchFilter]
    search_text = ['title', 'file_name']

class VacancyViewSet(viewsets.ModelViewSet):
    serializer_class = VacancySerializer
    permission_classes = [SectionPermission]
    section = 'vacancies'
    pagination_class = VacancyPagination
    filter_backends = [ListSearchFilter]
    search_text = ['title_ru', 'title_ky']

    def get_queryset(self):
        queryset = Vacancy.objects.all().order_by('-created_at')
        params = self.request.query_params
        manager_view = can_edit_section(self.request.user, self.section) and (
            self.action != 'list' or params.get('all') == '1'
        )
        if not manager_view:
            return queryset.filter(is_active=True)
        is_active = params.get('is_active')
        if self.action == 'list' and is_active in ('1', '0'):
            queryset = queryset.filter(is_active=is_active == '1')
        return queryset

class ApplicationPermission(BasePermission):
    def has_permission(self, request, view):
        return view.action == 'create' or can_edit_section(request.user, 'vacancies')


class ApplicationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class VacancyApplicationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [ApplicationPermission]
    pagination_class = ApplicationPagination
    filter_backends = [ListSearchFilter]
    search_text = ['full_name', 'email', 'vacancy_title']
    search_phone = ['phone']
    throttle_scope = 'vacancy_applications'

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.action == 'create' else []

    def get_queryset(self):
        queryset = VacancyApplication.objects.defer('resume_content')
        status_filter = self.request.query_params.get('status')
        if status_filter in dict(VacancyApplication.STATUS_CHOICES):
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_serializer_class(self):
        return VacancyApplicationCreateSerializer if self.action == 'create' else VacancyApplicationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data.get('website'):
            serializer.save()
        return Response({'ok': True}, status=status.HTTP_201_CREATED)

    def export(self, request):
        return applications_export_response()

    def resume(self, request, pk=None):
        application = self.get_object()
        return HttpResponse(
            bytes(application.resume_content),
            content_type=application.resume_type,
            headers={
                'Content-Disposition': content_disposition_header(True, application.resume_name),
                'Cache-Control': 'no-store',
            },
        )

def has_intake_token(request):
    expected = settings.COMPLAINTS_INTAKE_TOKEN
    provided = request.headers.get('X-Intake-Token', '')
    if len(expected) < 32 or not provided:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


class ComplaintPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return has_intake_token(request)
        if view.action == 'destroy':
            return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
        return can_edit_section(request.user, 'complaints')


class ComplaintPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ComplaintViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [ComplaintPermission]
    pagination_class = ComplaintPagination
    filter_backends = [ListSearchFilter]
    search_text = ['full_name', 'email', 'subject', 'description', 'incident_location']
    search_phone = ['phone']

    def get_queryset(self):
        photos = ComplaintPhoto.objects.defer('content')
        queryset = Complaint.objects.prefetch_related(Prefetch('photos', queryset=photos))
        params = self.request.query_params
        status_filter = params.get('status')
        if status_filter in dict(Complaint.STATUS_CHOICES):
            queryset = queryset.filter(status=status_filter)
        type_filter = params.get('complaint_type')
        if type_filter in dict(Complaint.TYPE_CHOICES):
            queryset = queryset.filter(complaint_type=type_filter)
        return queryset

    def get_serializer_class(self):
        return ComplaintCreateSerializer if self.action == 'create' else ComplaintSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complaint = serializer.save()
        return Response({'id': str(complaint.id)}, status=status.HTTP_201_CREATED)

    def photo(self, request, pk=None, photo_id=None):
        complaint = self.get_object()
        photo = get_object_or_404(ComplaintPhoto, pk=photo_id, complaint=complaint)
        extension = photo.content_type.split('/')[-1].replace('jpeg', 'jpg')
        return HttpResponse(
            bytes(photo.content),
            content_type=photo.content_type,
            headers={
                'Content-Disposition': content_disposition_header(False, f'zhaloba-foto-{photo.position + 1}.{extension}'),
                'Cache-Control': 'no-store',
            },
        )

class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            log_login_success(request, request.data.get('username'))
            set_auth_cookies(response, response.data['access'], response.data['refresh'])
            response.data = {'ok': True}
        return response

    def throttled(self, request, wait):
        log_login_throttled(request)
        super().throttled(request, wait)


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_refresh'

    def post(self, request, *args, **kwargs):
        require_admin_origin(request)
        serializer = self.get_serializer(data={'refresh': request.COOKIES.get(REFRESH_COOKIE) or 'none'})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            raise InvalidToken(error.args[0])

        response = Response({'ok': True})
        set_auth_cookies(response, serializer.validated_data['access'], serializer.validated_data['refresh'])
        return response


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_refresh'

    def post(self, request):
        require_admin_origin(request)
        raw_token = request.COOKIES.get(REFRESH_COOKIE)
        if raw_token:
            try:
                RefreshToken(raw_token).blacklist()
            except TokenError:
                pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        delete_auth_cookies(response)
        return response

class SiteSettingsView(APIView):
    permission_classes = [SectionPermission]
    section = 'site_settings'

    def get(self, request):
        return Response(SiteSettingsSerializer(SiteSettings.load()).data)

    def patch(self, request):
        serializer = SiteSettingsSerializer(SiteSettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info('Оформление сайта изменил %s: %s', request.user.username, serializer.validated_data)
        return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response({
        'username': user.username,
        'is_superuser': user.is_superuser,
        'groups': list(user.groups.values_list('name', flat=True)),
    })

@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok', 'message': 'Server is running'})