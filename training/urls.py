from rest_framework.routers import DefaultRouter

from training.views import (
    CompetencyViewSet,
    CriticalActivityRuleViewSet,
    JobPositionViewSet,
    TrainingEnrollmentViewSet,
    TrainingIndicatorReportViewSet,
    TrainingMatrixRequirementViewSet,
    TrainingRequirementViewSet,
    TrainingSessionViewSet,
    WorkFunctionViewSet,
)


app_name = 'training'

router = DefaultRouter()
router.register('job-positions', JobPositionViewSet, basename='job-position')
router.register('functions', WorkFunctionViewSet, basename='function')
router.register('competencies', CompetencyViewSet, basename='competency')
router.register('requirements', TrainingRequirementViewSet, basename='requirement')
router.register('matrix', TrainingMatrixRequirementViewSet, basename='matrix')
router.register('sessions', TrainingSessionViewSet, basename='session')
router.register('enrollments', TrainingEnrollmentViewSet, basename='enrollment')
router.register('critical-activities', CriticalActivityRuleViewSet, basename='critical-activity')
router.register('reports', TrainingIndicatorReportViewSet, basename='report')

urlpatterns = router.urls
