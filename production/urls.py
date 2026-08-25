from rest_framework.routers import DefaultRouter

from production.views import (
    MaterialConsumptionViewSet,
    ProductionLaborEntryViewSet,
    ProductionOperationExecutionViewSet,
    ProductionOrderViewSet,
    ProductionOutputViewSet,
)


app_name = 'production'

router = DefaultRouter()
router.register('orders', ProductionOrderViewSet, basename='order')
router.register('consumptions', MaterialConsumptionViewSet, basename='consumption')
router.register('outputs', ProductionOutputViewSet, basename='output')
router.register('operations', ProductionOperationExecutionViewSet, basename='operation')
router.register('labor-entries', ProductionLaborEntryViewSet, basename='labor-entry')

urlpatterns = router.urls
