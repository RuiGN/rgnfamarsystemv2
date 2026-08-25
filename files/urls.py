from rest_framework.routers import DefaultRouter

from files.views import (
    ProtectedFileAccessRuleViewSet,
    ProtectedFileAuditTrailViewSet,
    ProtectedFileViewSet,
    SecureFileLinkViewSet,
)


app_name = 'files'

router = DefaultRouter()
router.register('protected-files', ProtectedFileViewSet, basename='protected-file')
router.register('access-rules', ProtectedFileAccessRuleViewSet, basename='access-rule')
router.register('secure-links', SecureFileLinkViewSet, basename='secure-link')
router.register('audit-trail', ProtectedFileAuditTrailViewSet, basename='audit-trail')

urlpatterns = router.urls
