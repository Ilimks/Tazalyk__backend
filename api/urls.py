from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from django.http import JsonResponse
from . import views
from .search import SearchView

router = DefaultRouter()
router.register(r'videos', views.VideoViewSet)
router.register(r'photos', views.PhotoViewSet)
router.register(r'news', views.NewsViewSet)
router.register(r'procurements', views.ProcurementViewSet)
router.register(r'local-acts', views.LocalActViewSet)
router.register(r'legislation', views.LegislationViewSet)

def health_check(request):
    return JsonResponse({
        'status': 'ok',
        'message': 'Server is running'
    })

urlpatterns = [
    # JWT endpoints (с ограничением числа попыток)
    path('token/', views.ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', views.ThrottledTokenRefreshView.as_view(), name='token_refresh'),
    
    # API endpoints
    re_path(r'^videos/?$', views.VideoViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^videos/(?P<pk>[^/.]+)/?$', views.VideoViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    re_path(r'^photos/?$', views.PhotoViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^photos/(?P<pk>[^/.]+)/?$', views.PhotoViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    re_path(r'^news/?$', views.NewsViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^news/(?P<pk>[^/.]+)/?$', views.NewsViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    re_path(r'^procurements/?$', views.ProcurementViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^procurements/(?P<pk>[^/.]+)/?$', views.ProcurementViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    re_path(r'^local-acts/?$', views.LocalActViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^local-acts/(?P<pk>[^/.]+)/?$', views.LocalActViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    re_path(r'^legislation/?$', views.LegislationViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^legislation/(?P<pk>[^/.]+)/?$', views.LegislationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    # PATCH — включить/отключить вакансию одним полем is_active
    re_path(r'^vacancies/?$', views.VacancyViewSet.as_view({'get': 'list', 'post': 'create'})),
    re_path(r'^vacancies/(?P<pk>[^/.]+)/?$', views.VacancyViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})),
    
    path('search/', SearchView.as_view()),
    path('health/', health_check),
    path('me/', views.me),
]