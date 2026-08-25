from rest_framework.routers import DefaultRouter

from reports.views import (
    DashboardWidgetViewSet,
    DashboardWorkspaceViewSet,
    ReportDefinitionViewSet,
    ReportExecutionViewSet,
    ReportNotificationViewSet,
    ReportScheduleViewSet,
)


app_name = 'reports'

router = DefaultRouter()
router.register('dashboards', DashboardWorkspaceViewSet, basename='dashboard')
router.register('dashboard-widgets', DashboardWidgetViewSet, basename='dashboard-widget')
router.register('definitions', ReportDefinitionViewSet, basename='definition')
router.register('executions', ReportExecutionViewSet, basename='execution')
router.register('schedules', ReportScheduleViewSet, basename='schedule')
router.register('notifications', ReportNotificationViewSet, basename='notification')

urlpatterns = router.urls
