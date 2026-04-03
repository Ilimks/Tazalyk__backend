# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.decorators.csrf import csrf_exempt
from . import views

router = DefaultRouter()
router.register(r'videos', views.VideoViewSet)
router.register(r'photos', views.PhotoViewSet)
router.register(r'news', views.NewsViewSet)
router.register(r'procurements', views.ProcurementViewSet)
router.register(r'vacancies', views.VacancyViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('admin-login/', views.admin_login, name='admin_login'),
    path('import-data/', views.import_local_data, name='import_data'),
]