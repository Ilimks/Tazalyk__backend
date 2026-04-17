from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def home(request):
    return JsonResponse({
        'message': 'Добро пожаловать в API МП "Тазалык"',
        'endpoints': {
            'admin': '/admin/',
            'api': '/api/',
            'api_token': '/api/token/',
            'api_token_refresh': '/api/token/refresh/',
            'videos': '/api/videos/',
            'photos': '/api/photos/',
            'news': '/api/news/',
            'procurements': '/api/procurements/',
            'local_acts': '/api/local-acts/',
            'legislation': '/api/legislation/',
        }
    })

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]