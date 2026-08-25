from rest_framework.routers import DefaultRouter

from pharmacovigilance.views import (
    PharmacovigilanceActionViewSet,
    PharmacovigilanceCaseViewSet,
    PharmacovigilanceCausalityAssessmentViewSet,
    PharmacovigilanceClassificationViewSet,
    PharmacovigilanceInvestigationViewSet,
    PharmacovigilanceLinkViewSet,
    PharmacovigilanceSafetyReportViewSet,
)


app_name = 'pharmacovigilance'

router = DefaultRouter()
router.register('cases', PharmacovigilanceCaseViewSet, basename='case')
router.register(
    'classifications', PharmacovigilanceClassificationViewSet, basename='classification'
)
router.register(
    'causality-assessments',
    PharmacovigilanceCausalityAssessmentViewSet,
    basename='causality-assessment',
)
router.register('investigations', PharmacovigilanceInvestigationViewSet, basename='investigation')
router.register('actions', PharmacovigilanceActionViewSet, basename='action')
router.register('links', PharmacovigilanceLinkViewSet, basename='link')
router.register('reports', PharmacovigilanceSafetyReportViewSet, basename='report')

urlpatterns = router.urls
