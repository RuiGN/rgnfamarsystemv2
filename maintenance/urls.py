from rest_framework.routers import DefaultRouter

from maintenance.views import (
    EquipmentAssetViewSet,
    EquipmentDowntimeViewSet,
    EquipmentUsageLogViewSet,
    MaintenanceMetricReportViewSet,
    MaintenanceOrderViewSet,
    MaintenancePlanViewSet,
)


app_name = 'maintenance'

router = DefaultRouter()
router.register('assets', EquipmentAssetViewSet, basename='asset')
router.register('plans', MaintenancePlanViewSet, basename='plan')
router.register('orders', MaintenanceOrderViewSet, basename='order')
router.register('downtimes', EquipmentDowntimeViewSet, basename='downtime')
router.register('usage-logs', EquipmentUsageLogViewSet, basename='usage-log')
router.register('reports', MaintenanceMetricReportViewSet, basename='report')

urlpatterns = router.urls
