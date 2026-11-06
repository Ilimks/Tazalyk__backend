from decimal import Decimal, InvalidOperation

from django.db.models import Max, Min, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .exports import orders_export_response
from .models import Order, Product
from .permissions import OrderPermission, ProductPermission, is_shop_manager
from .serializers import OrderCreateSerializer, OrderSerializer, ProductSerializer
from .contacts import manager_links
from .telegram import send_order_notification


# ========== ПАГИНАЦИЯ ==========
class ProductPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 48


class OrderPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ?ordering= на странице магазина
PRODUCT_ORDERINGS = {
    'price': ('price', 'sort_order'),
    '-price': ('-price', 'sort_order'),
    'volume': ('volume', 'price'),
    '-volume': ('-volume', 'price'),
    'new': ('-created_at',),
}
MATERIALS = {value for value, _ in Product.MATERIAL_CHOICES}
TRUE_VALUES = ('1', 'true')


def _split(value):
    return [part.strip() for part in value.split(',') if part.strip()] if value else []


def _decimal(value):
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


# ========== ТОВАРЫ ==========
class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [ProductPermission]
    pagination_class = ProductPagination

    def get_queryset(self):
        params = self.request.query_params
        queryset = Product.objects.all()

        # скрытые товары видны только менеджерам: при редактировании и в списке с ?all=1
        manager_view = is_shop_manager(self.request.user) and (self.action != 'list' or params.get('all') == '1')
        if not manager_view:
            queryset = queryset.filter(is_active=True)
        if self.action != 'list':
            return queryset

        volumes = [int(v) for v in _split(params.get('volume')) if v.isdigit()]
        if volumes:
            queryset = queryset.filter(volume__in=volumes)
        materials = [m for m in _split(params.get('material')) if m in MATERIALS]
        if materials:
            queryset = queryset.filter(material__in=materials)
        price_min = _decimal(params.get('price_min'))
        if price_min is not None:
            queryset = queryset.filter(price__gte=price_min)
        price_max = _decimal(params.get('price_max'))
        if price_max is not None:
            queryset = queryset.filter(price__lte=price_max)
        if params.get('in_stock') in TRUE_VALUES:
            queryset = queryset.filter(in_stock=True)
        if params.get('featured') in TRUE_VALUES:
            queryset = queryset.filter(is_featured=True)
        search = params.get('q', '').strip()[:100]
        if search:
            queryset = queryset.filter(Q(name_ru__icontains=search) | Q(name_ky__icontains=search))

        ordering = PRODUCT_ORDERINGS.get(params.get('ordering'))
        return queryset.order_by(*ordering) if ordering else queryset

    @action(detail=False, methods=['get'], url_path='filters')
    def filters(self, request):
        """Варианты для фильтров магазина: какие объёмы и материалы есть, диапазон цен"""
        active = Product.objects.filter(is_active=True)
        present = set(active.values_list('material', flat=True))
        prices = active.aggregate(min=Min('price'), max=Max('price'))
        return Response({
            'volumes': sorted(set(active.values_list('volume', flat=True))),
            'materials': [{'value': v, 'label': label} for v, label in Product.MATERIAL_CHOICES if v in present],
            # строкой, как цены в остальных ответах
            'price': {k: (str(v) if v is not None else None) for k, v in prices.items()},
        })

    def perform_update(self, serializer):
        old_image = serializer.instance.image
        old_name, storage = old_image.name, old_image.storage
        instance = serializer.save()
        # заменённое или удалённое фото не должно оставаться на диске
        if old_name and instance.image.name != old_name:
            storage.delete(old_name)

    def perform_destroy(self, instance):
        if instance.image:
            instance.image.delete(save=False)
        instance.delete()


# ========== ЗАКАЗЫ ==========
class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [OrderPermission]
    pagination_class = OrderPagination
    throttle_scope = 'shop_orders'

    def get_throttles(self):
        # ограничение частоты — только на оформление заказа с сайта
        return [ScopedRateThrottle()] if self.action == 'create' else []

    def get_queryset(self):
        queryset = Order.objects.prefetch_related('items')
        status_filter = self.request.query_params.get('status')
        if status_filter in dict(Order.STATUS_CHOICES):
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_serializer_class(self):
        return OrderCreateSerializer if self.action == 'create' else OrderSerializer

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """GET /api/shop/orders/export/ — проданные и отклонённые товары файлом .xlsx"""
        return orders_export_response()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        if send_order_notification(order):
            order.telegram_notified = True
            order.save(update_fields=['telegram_notified'])

        return Response(
            {
                'number': order.id,
                'total': str(order.total),
                'contact_method': order.contact_method,
                **manager_links(order),
            },
            status=status.HTTP_201_CREATED,
        )
