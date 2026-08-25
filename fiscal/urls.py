from rest_framework.routers import DefaultRouter

from fiscal.views import (
    FiscalAuditTrailViewSet,
    FiscalBookEntryViewSet,
    FiscalCompanyViewSet,
    FiscalDocumentItemViewSet,
    FiscalDocumentViewSet,
    FiscalEmailDeliveryViewSet,
    FiscalEmissionEventViewSet,
    FiscalMunicipalityViewSet,
    FiscalNCMViewSet,
    FiscalObligationViewSet,
    FiscalOperationCodeViewSet,
    FiscalTaxViewSet,
    FiscalUnitViewSet,
    TaxAssessmentPeriodViewSet,
    TaxRuleViewSet,
    TaxSituationViewSet,
)


app_name = 'fiscal'

router = DefaultRouter()
router.register('companies', FiscalCompanyViewSet, basename='company')
router.register('municipalities', FiscalMunicipalityViewSet, basename='municipality')
router.register('units', FiscalUnitViewSet, basename='unit')
router.register('ncms', FiscalNCMViewSet, basename='ncm')
router.register('cfops', FiscalOperationCodeViewSet, basename='cfop')
router.register('tax-situations', TaxSituationViewSet, basename='tax-situation')
router.register('tax-rules', TaxRuleViewSet, basename='tax-rule')
router.register('documents', FiscalDocumentViewSet, basename='document')
router.register('document-items', FiscalDocumentItemViewSet, basename='document-item')
router.register('taxes', FiscalTaxViewSet, basename='tax')
router.register('emission-events', FiscalEmissionEventViewSet, basename='emission-event')
router.register('email-deliveries', FiscalEmailDeliveryViewSet, basename='email-delivery')
router.register('assessments', TaxAssessmentPeriodViewSet, basename='assessment')
router.register('book-entries', FiscalBookEntryViewSet, basename='book-entry')
router.register('obligations', FiscalObligationViewSet, basename='obligation')
router.register('audit-trail', FiscalAuditTrailViewSet, basename='audit-trail')

urlpatterns = router.urls
