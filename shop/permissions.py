from rest_framework.permissions import SAFE_METHODS, BasePermission

SHOP_GROUP = 'shop_managers'


def is_shop_manager(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=SHOP_GROUP).exists()


class ProductPermission(BasePermission):
    """Каталог читают все, менять могут менеджеры магазина и администратор"""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_shop_manager(request.user)


class OrderPermission(BasePermission):
    """Оформить заказ может любой посетитель, смотреть и менять заказы — только менеджеры.
    Удалять заказы может только администратор: это история продаж."""

    def has_permission(self, request, view):
        if view.action == 'create':
            return True
        if view.action == 'destroy':
            return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
        return is_shop_manager(request.user)
