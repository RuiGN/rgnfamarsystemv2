from rest_framework.routers import DefaultRouter

from crm.views import (
    CampaignViewSet,
    CustomerComplaintViewSet,
    CustomerContactViewSet,
    CustomerGroupViewSet,
    CustomerInteractionViewSet,
    CustomerProfileViewSet,
    OpportunityViewSet,
    SalesChannelViewSet,
    SalesContractViewSet,
    SalesOrderItemViewSet,
    SalesOrderViewSet,
    SalesProposalItemViewSet,
    SalesProposalViewSet,
    SalesRepresentativeViewSet,
)


app_name = 'crm'

router = DefaultRouter()
router.register('customer-groups', CustomerGroupViewSet, basename='customer-group')
router.register('channels', SalesChannelViewSet, basename='channel')
router.register('representatives', SalesRepresentativeViewSet, basename='representative')
router.register('customer-profiles', CustomerProfileViewSet, basename='customer-profile')
router.register('contacts', CustomerContactViewSet, basename='contact')
router.register('campaigns', CampaignViewSet, basename='campaign')
router.register('opportunities', OpportunityViewSet, basename='opportunity')
router.register('proposals', SalesProposalViewSet, basename='proposal')
router.register('proposal-items', SalesProposalItemViewSet, basename='proposal-item')
router.register('contracts', SalesContractViewSet, basename='contract')
router.register('orders', SalesOrderViewSet, basename='order')
router.register('order-items', SalesOrderItemViewSet, basename='order-item')
router.register('interactions', CustomerInteractionViewSet, basename='interaction')
router.register('complaints', CustomerComplaintViewSet, basename='complaint')

urlpatterns = router.urls
