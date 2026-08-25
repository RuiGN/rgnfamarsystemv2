from rest_framework.routers import DefaultRouter

from procurement.views import (
    PurchaseOrderItemViewSet,
    PurchaseOrderViewSet,
    PurchaseReceiptItemViewSet,
    PurchaseReceiptViewSet,
    PurchaseRequisitionItemViewSet,
    PurchaseRequisitionViewSet,
    QuotationRequestViewSet,
    SupplierQualificationEventViewSet,
    SupplierQuotationViewSet,
)


app_name = 'procurement'

router = DefaultRouter()
router.register('requisitions', PurchaseRequisitionViewSet, basename='requisition')
router.register('requisition-items', PurchaseRequisitionItemViewSet, basename='requisition-item')
router.register('rfqs', QuotationRequestViewSet, basename='rfq')
router.register('supplier-quotations', SupplierQuotationViewSet, basename='supplier-quotation')
router.register(
    'supplier-qualification-events',
    SupplierQualificationEventViewSet,
    basename='supplier-qualification-event',
)
router.register('orders', PurchaseOrderViewSet, basename='order')
router.register('order-items', PurchaseOrderItemViewSet, basename='order-item')
router.register('receipts', PurchaseReceiptViewSet, basename='receipt')
router.register('receipt-items', PurchaseReceiptItemViewSet, basename='receipt-item')

urlpatterns = router.urls
