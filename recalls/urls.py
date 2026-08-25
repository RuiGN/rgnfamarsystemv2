from rest_framework.routers import DefaultRouter

from recalls.views import (
    MarketComplaintViewSet,
    ProductReturnViewSet,
    RecallCampaignViewSet,
    RecallCommunicationViewSet,
    RecallEffectivenessReportViewSet,
    RecallImpactedCustomerViewSet,
)


app_name = 'recalls'

router = DefaultRouter()
router.register('complaints', MarketComplaintViewSet, basename='complaint')
router.register('returns', ProductReturnViewSet, basename='return')
router.register('campaigns', RecallCampaignViewSet, basename='campaign')
router.register('impacted-customers', RecallImpactedCustomerViewSet, basename='impacted-customer')
router.register('communications', RecallCommunicationViewSet, basename='communication')
router.register('reports', RecallEffectivenessReportViewSet, basename='report')

urlpatterns = router.urls
