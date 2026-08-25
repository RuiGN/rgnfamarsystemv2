from rest_framework.routers import DefaultRouter

from planning.views import (
    CapacityLoadViewSet,
    CapacityResourceViewSet,
    InventoryPositionViewSet,
    MPSLineViewSet,
    MRPRunViewSet,
    MRPSuggestionViewSet,
    MasterProductionScheduleViewSet,
    PlanningPolicyViewSet,
)


app_name = 'planning'

router = DefaultRouter()
router.register('policies', PlanningPolicyViewSet, basename='policy')
router.register('schedules', MasterProductionScheduleViewSet, basename='schedule')
router.register('mps-lines', MPSLineViewSet, basename='mps-line')
router.register('inventory', InventoryPositionViewSet, basename='inventory-position')
router.register('mrp-runs', MRPRunViewSet, basename='mrp-run')
router.register('suggestions', MRPSuggestionViewSet, basename='suggestion')
router.register('capacity-resources', CapacityResourceViewSet, basename='capacity-resource')
router.register('capacity-loads', CapacityLoadViewSet, basename='capacity-load')

urlpatterns = router.urls
