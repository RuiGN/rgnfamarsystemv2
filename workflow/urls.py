from rest_framework.routers import DefaultRouter

from workflow.views import (
    ApprovalQueueViewSet,
    ApprovalTaskViewSet,
    AsyncJobStatusViewSet,
    WorkflowAttachmentViewSet,
    WorkflowCommentViewSet,
    WorkflowDelegationViewSet,
    WorkflowHistoryViewSet,
    WorkflowNotificationViewSet,
)


app_name = 'workflow'

router = DefaultRouter()
router.register('notifications', WorkflowNotificationViewSet, basename='notification')
router.register('approval-queues', ApprovalQueueViewSet, basename='approval-queue')
router.register('approval-tasks', ApprovalTaskViewSet, basename='approval-task')
router.register('delegations', WorkflowDelegationViewSet, basename='delegation')
router.register('comments', WorkflowCommentViewSet, basename='comment')
router.register('attachments', WorkflowAttachmentViewSet, basename='attachment')
router.register('async-jobs', AsyncJobStatusViewSet, basename='async-job')
router.register('history', WorkflowHistoryViewSet, basename='history')

urlpatterns = router.urls
