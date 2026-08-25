from rest_framework.routers import DefaultRouter

from qa.views import (
    BatchRecordChecklistItemViewSet,
    CriticalActivityRuleViewSet,
    LotReleaseViewSet,
    QAReviewViewSet,
    QualityBlockViewSet,
    TrainingRecordViewSet,
    TrainingRequirementViewSet,
)


app_name = 'qa'

router = DefaultRouter()
router.register('reviews', QAReviewViewSet, basename='review')
router.register('checklist-items', BatchRecordChecklistItemViewSet, basename='checklist-item')
router.register('lot-releases', LotReleaseViewSet, basename='lot-release')
router.register('blocks', QualityBlockViewSet, basename='block')
router.register(
    'training-requirements', TrainingRequirementViewSet, basename='training-requirement'
)
router.register('training-records', TrainingRecordViewSet, basename='training-record')
router.register(
    'critical-activity-rules', CriticalActivityRuleViewSet, basename='critical-activity-rule'
)

urlpatterns = router.urls
