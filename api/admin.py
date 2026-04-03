from django.contrib import admin
from .models import Video, Photo, News, Procurement, Vacancy

admin.site.register(Video)
admin.site.register(Photo)
admin.site.register(News)
admin.site.register(Procurement)
admin.site.register(Vacancy)