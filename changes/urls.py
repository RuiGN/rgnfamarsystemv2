from rest_framework.routers import DefaultRouter

from changes.views import (
    ChangeActionViewSet,
    ChangeAffectedItemViewSet,
    ChangeApprovalViewSet,
    ChangeAssessmentViewSet,
    ChangeControlViewSet,
    ChangeStockAssessmentViewSet,
)


app_name = 'changes'

router = DefaultRouter()
router.register('controls', ChangeControlViewSet, basename='control')
router.register('affected-items', ChangeAffectedItemViewSet, basename='affected-item')
router.register('assessments', ChangeAssessmentViewSet, basename='assessment')
router.register('actions', ChangeActionViewSet, basename='action')
router.register('approvals', ChangeApprovalViewSet, basename='approval')
router.register('stock-assessments', ChangeStockAssessmentViewSet, basename='stock-assessment')

urlpatterns = router.urls
