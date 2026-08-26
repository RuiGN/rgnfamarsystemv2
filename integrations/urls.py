from rest_framework.routers import DefaultRouter

from integrations.views import (
    ApiCallLogViewSet,
    ApiClientApplicationViewSet,
    IntegrationConnectorViewSet,
    IntegrationEventViewSet,
    LabelPrinterSettingsViewSet,
)


app_name = 'integrations'

router = DefaultRouter()
router.register('connectors', IntegrationConnectorViewSet, basename='connector')
router.register('label-printers', LabelPrinterSettingsViewSet, basename='label-printer')
router.register('api-clients', ApiClientApplicationViewSet, basename='api-client')
router.register('api-call-logs', ApiCallLogViewSet, basename='api-call-log')
router.register('events', IntegrationEventViewSet, basename='event')

urlpatterns = router.urls
