from rest_framework.routers import DefaultRouter

from inventory.views import (
    StockBalanceViewSet,
    StockLotGenealogyViewSet,
    StockLotViewSet,
    StockMovementViewSet,
)


app_name = 'inventory'

router = DefaultRouter()
router.register('lots', StockLotViewSet, basename='lot')
router.register('balances', StockBalanceViewSet, basename='balance')
router.register('movements', StockMovementViewSet, basename='movement')
router.register('genealogy', StockLotGenealogyViewSet, basename='genealogy')

urlpatterns = router.urls
