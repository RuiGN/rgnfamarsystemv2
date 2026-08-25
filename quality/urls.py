from rest_framework.routers import DefaultRouter

from quality.views import (
    AnalyticalSpecificationViewSet,
    LaboratoryInvestigationViewSet,
    QualityAnalysisViewSet,
    QualityDocumentViewSet,
    QualityResultViewSet,
    QualitySampleViewSet,
)


app_name = 'quality'

router = DefaultRouter()
router.register('specifications', AnalyticalSpecificationViewSet, basename='specification')
router.register('samples', QualitySampleViewSet, basename='sample')
router.register('analyses', QualityAnalysisViewSet, basename='analysis')
router.register('results', QualityResultViewSet, basename='result')
router.register('investigations', LaboratoryInvestigationViewSet, basename='investigation')
router.register('documents', QualityDocumentViewSet, basename='document')

urlpatterns = router.urls
