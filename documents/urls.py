from rest_framework.routers import DefaultRouter

from documents.views import (
    ControlledDocumentViewSet,
    DocumentApprovalViewSet,
    DocumentAttachmentViewSet,
    DocumentAuditTrailViewSet,
    DocumentDistributionViewSet,
    DocumentRelationshipViewSet,
)


app_name = 'documents'

router = DefaultRouter()
router.register('controlled-documents', ControlledDocumentViewSet, basename='controlled-document')
router.register('attachments', DocumentAttachmentViewSet, basename='attachment')
router.register('relationships', DocumentRelationshipViewSet, basename='relationship')
router.register('approvals', DocumentApprovalViewSet, basename='approval')
router.register('distributions', DocumentDistributionViewSet, basename='distribution')
router.register('audit-trail', DocumentAuditTrailViewSet, basename='audit-trail')

urlpatterns = router.urls
