from rest_framework.routers import DefaultRouter

from ai_agents.views import (
    AIAgentProfileViewSet,
    AIAgentRunViewSet,
    AIInsightSuggestionViewSet,
    AIPromptAuditLogViewSet,
)


app_name = 'ai_agents'

router = DefaultRouter()
router.register('profiles', AIAgentProfileViewSet, basename='profile')
router.register('runs', AIAgentRunViewSet, basename='run')
router.register('suggestions', AIInsightSuggestionViewSet, basename='suggestion')
router.register('audit-logs', AIPromptAuditLogViewSet, basename='audit-log')

urlpatterns = router.urls
