from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.http import JsonResponse
from . import views

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
    # JWT endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
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
    
    path('health/', health_check),
    path('admin-login/', views.admin_login),
    path('import-data/', views.import_local_data),
]