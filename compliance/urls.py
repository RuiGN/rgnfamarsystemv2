from rest_framework.routers import DefaultRouter

from compliance.views import (
    ComplianceChecklistItemViewSet,
    CriticalActionExecutionViewSet,
    RecordStatusHistoryViewSet,
    TransversalRequirementPolicyViewSet,
)


app_name = 'compliance'

router = DefaultRouter()
router.register('policies', TransversalRequirementPolicyViewSet, basename='policy')
router.register('status-history', RecordStatusHistoryViewSet, basename='status-history')
router.register('critical-actions', CriticalActionExecutionViewSet, basename='critical-action')
router.register('checklist-items', ComplianceChecklistItemViewSet, basename='checklist-item')

urlpatterns = router.urls
