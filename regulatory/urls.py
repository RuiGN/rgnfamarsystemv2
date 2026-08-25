from rest_framework.routers import DefaultRouter

from regulatory.views import (
    RegulatoryAlertViewSet,
    RegulatoryCommitmentViewSet,
    RegulatoryDossierViewSet,
    RegulatoryEvidenceViewSet,
    RegulatoryLinkViewSet,
    RegulatoryPetitionViewSet,
    RegulatoryProductViewSet,
    RegulatoryRegistrationViewSet,
    RegulatoryReportViewSet,
    RegulatoryRequirementViewSet,
)


app_name = 'regulatory'

router = DefaultRouter()
router.register('products', RegulatoryProductViewSet, basename='product')
router.register('dossiers', RegulatoryDossierViewSet, basename='dossier')
router.register('registrations', RegulatoryRegistrationViewSet, basename='registration')
router.register('petitions', RegulatoryPetitionViewSet, basename='petition')
router.register('requirements', RegulatoryRequirementViewSet, basename='requirement')
router.register('commitments', RegulatoryCommitmentViewSet, basename='commitment')
router.register('evidences', RegulatoryEvidenceViewSet, basename='evidence')
router.register('links', RegulatoryLinkViewSet, basename='link')
router.register('reports', RegulatoryReportViewSet, basename='report')
router.register('alerts', RegulatoryAlertViewSet, basename='alert')

urlpatterns = router.urls
