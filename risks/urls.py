from rest_framework.routers import DefaultRouter

from risks.views import (
    RiskAlertViewSet,
    RiskAssessmentViewSet,
    RiskControlViewSet,
    RiskLinkViewSet,
    RiskMitigationActionViewSet,
    RiskRecordViewSet,
    RiskReviewViewSet,
)


app_name = 'risks'

router = DefaultRouter()
router.register('records', RiskRecordViewSet, basename='record')
router.register('assessments', RiskAssessmentViewSet, basename='assessment')
router.register('controls', RiskControlViewSet, basename='control')
router.register('actions', RiskMitigationActionViewSet, basename='action')
router.register('links', RiskLinkViewSet, basename='link')
router.register('reviews', RiskReviewViewSet, basename='review')
router.register('alerts', RiskAlertViewSet, basename='alert')

urlpatterns = router.urls
