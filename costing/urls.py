from rest_framework.routers import DefaultRouter

from costing.views import (
    CostElementViewSet,
    CostReportSnapshotViewSet,
    CostSimulationViewSet,
    MonthlyCostClosingViewSet,
    ProductionCostCaptureViewSet,
    StandardCostViewSet,
)


app_name = 'costing'

router = DefaultRouter()
router.register('cost-elements', CostElementViewSet, basename='cost-element')
router.register('standard-costs', StandardCostViewSet, basename='standard-cost')
router.register('simulations', CostSimulationViewSet, basename='simulation')
router.register('production-captures', ProductionCostCaptureViewSet, basename='production-capture')
router.register('monthly-closings', MonthlyCostClosingViewSet, basename='monthly-closing')
router.register('report-snapshots', CostReportSnapshotViewSet, basename='report-snapshot')

urlpatterns = router.urls
