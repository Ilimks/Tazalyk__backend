from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register('products', views.ProductViewSet, basename='shop-product')
router.register('orders', views.OrderViewSet, basename='shop-order')

urlpatterns = router.urls
