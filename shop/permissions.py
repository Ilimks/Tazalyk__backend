from rest_framework.permissions import SAFE_METHODS, BasePermission

SHOP_GROUP = 'shop_managers'


def is_shop_manager(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=SHOP_GROUP).exists()


class ProductPermission(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_shop_manager(request.user)


class OrderPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return True
        if view.action == 'destroy':
            return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
        return is_shop_manager(request.user)
