from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def home(request):
    return JsonResponse({
        'message': 'Добро пожаловать в API МП "Тазалык"',
        'endpoints': {
            'admin': '/admin/',
            'api': '/api/',
            'videos': '/api/videos/',
            'photos': '/api/photos/',
            'news': '/api/news/',
            'procurements': '/api/procurements/',
            'vacancies': '/api/vacancies/',
        }
    })

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]