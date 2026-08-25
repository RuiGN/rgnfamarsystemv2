from rest_framework.routers import DefaultRouter

from governance.views import (
    DemoScenarioLoadViewSet,
    GovernanceAuditLogViewSet,
    GovernanceCatalogItemViewSet,
    GovernanceParameterViewSet,
    InstitutionSettingsViewSet,
    TechnicalResponsibleViewSet,
)


app_name = 'governance'

router = DefaultRouter()
router.register('parameters', GovernanceParameterViewSet, basename='parameter')
router.register('institution-settings', InstitutionSettingsViewSet, basename='institution-settings')
router.register(
    'technical-responsibles',
    TechnicalResponsibleViewSet,
    basename='technical-responsible',
)
router.register('catalog-items', GovernanceCatalogItemViewSet, basename='catalog-item')
router.register('audit-logs', GovernanceAuditLogViewSet, basename='audit-log')
router.register('demo-loads', DemoScenarioLoadViewSet, basename='demo-load')

urlpatterns = router.urls
