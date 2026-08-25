from rest_framework.routers import DefaultRouter

from formulations.views import (
    FormulaComponentViewSet,
    ManufacturingRouteViewSet,
    MasterFormulaViewSet,
    RouteStepViewSet,
)


app_name = 'formulations'

router = DefaultRouter()
router.register('formulas', MasterFormulaViewSet, basename='formula')
router.register('components', FormulaComponentViewSet, basename='component')
router.register('routes', ManufacturingRouteViewSet, basename='route')
router.register('steps', RouteStepViewSet, basename='step')

urlpatterns = router.urls
