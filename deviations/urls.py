from rest_framework.routers import DefaultRouter

from deviations.views import (
    DeviationApprovalViewSet,
    DeviationEvidenceViewSet,
    DeviationImpactAssessmentViewSet,
    DeviationInvestigationViewSet,
    DeviationLinkViewSet,
    QualityEventViewSet,
)


app_name = 'deviations'

router = DefaultRouter()
router.register('events', QualityEventViewSet, basename='event')
router.register('evidences', DeviationEvidenceViewSet, basename='evidence')
router.register('investigations', DeviationInvestigationViewSet, basename='investigation')
router.register(
    'impact-assessments', DeviationImpactAssessmentViewSet, basename='impact-assessment'
)
router.register('approvals', DeviationApprovalViewSet, basename='approval')
router.register('links', DeviationLinkViewSet, basename='link')

urlpatterns = router.urls
