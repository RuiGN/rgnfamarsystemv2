from rest_framework.routers import DefaultRouter

from audits.views import (
    AuditChecklistItemViewSet,
    AuditEvidenceViewSet,
    AuditFindingLinkViewSet,
    AuditFindingViewSet,
    AuditFollowUpActionViewSet,
    AuditPlanViewSet,
    AuditProgramViewSet,
    AuditReportViewSet,
)


app_name = 'audits'

router = DefaultRouter()
router.register('programs', AuditProgramViewSet, basename='program')
router.register('plans', AuditPlanViewSet, basename='plan')
router.register('checklist-items', AuditChecklistItemViewSet, basename='checklist-item')
router.register('findings', AuditFindingViewSet, basename='finding')
router.register('evidences', AuditEvidenceViewSet, basename='evidence')
router.register('actions', AuditFollowUpActionViewSet, basename='action')
router.register('finding-links', AuditFindingLinkViewSet, basename='finding-link')
router.register('reports', AuditReportViewSet, basename='report')

urlpatterns = router.urls
