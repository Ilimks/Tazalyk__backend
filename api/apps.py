from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        # регистрирует обработчик неудачных входов
        from . import security_events  # noqa: F401
