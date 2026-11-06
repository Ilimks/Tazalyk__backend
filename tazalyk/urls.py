from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse

from api.media_files import serve_media

# Карту всех адресов (включая /admin/) не публикуем — она только помогает подбирать вход
def home(request):
    return JsonResponse({'message': 'API МП «Тазалык»'})

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/shop/', include('shop.urls')),
    path('api/', include('api.urls')),
    # Фото товаров, видео и превью. На сервере nginx может отдавать MEDIA_ROOT сам — тогда это правило не сработает.
    re_path(r'^media/(?P<path>.*)$', serve_media),
]