from rest_framework.routers import DefaultRouter

from capa.views import (
    CapaActionViewSet,
    CapaApprovalViewSet,
    CapaEvidenceViewSet,
    CapaNotificationViewSet,
    CapaRecordViewSet,
    EffectivenessCheckViewSet,
)


app_name = 'capa'

router = DefaultRouter()
router.register('records', CapaRecordViewSet, basename='record')
router.register('actions', CapaActionViewSet, basename='action')
router.register('evidences', CapaEvidenceViewSet, basename='evidence')
router.register('effectiveness-checks', EffectivenessCheckViewSet, basename='effectiveness-check')
router.register('approvals', CapaApprovalViewSet, basename='approval')
router.register('notifications', CapaNotificationViewSet, basename='notification')

urlpatterns = router.urls
