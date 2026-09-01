from django.contrib import admin
from base.admin_mixins import GxpRetentionModelAdmin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from training.models import (
    Competency,
    CriticalActivityRule,
    JobPosition,
    TrainingEnrollment,
    TrainingIndicatorReport,
    TrainingMatrixRequirement,
    TrainingRequirement,
    TrainingSession,
    WorkFunction,
)


@admin.register(JobPosition)
class JobPositionAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = ('code', 'title', 'area', 'department', 'is_active')
    list_filter = ('area', 'department', 'is_active')
    search_fields = ('code', 'title', 'area', 'department', 'description')


@admin.register(WorkFunction)
class WorkFunctionAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = ('code', 'name', 'job_position', 'area', 'process', 'is_critical', 'is_active')
    list_filter = ('area', 'process', 'is_critical', 'is_active')
    search_fields = ('code', 'name', 'area', 'process', 'description', 'job_position__title')
    autocomplete_fields = ('job_position',)


@admin.register(Competency)
class CompetencyAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = ('code', 'name', 'competency_type', 'is_active')
    list_filter = ('competency_type', 'is_active')
    search_fields = ('code', 'name', 'description')


@admin.register(TrainingRequirement)
class TrainingRequirementAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = (
        'code',
        'title',
        'training_type',
        'area',
        'process',
        'is_mandatory',
        'block_without_valid_training',
        'is_active',
    )
    list_filter = (
        'training_type',
        'area',
        'process',
        'is_mandatory',
        'block_without_valid_training',
        'is_active',
    )
    search_fields = (
        'code',
        'title',
        'area',
        'process',
        'module_code',
        'regulatory_requirement_reference',
        'notes',
    )
    autocomplete_fields = ('job_position', 'function', 'competency', 'document')


@admin.register(TrainingMatrixRequirement)
class TrainingMatrixRequirementAdmin(GxpRetentionModelAdmin):
    list_display = (
        'job_position',
        'function',
        'competency',
        'requirement',
        'is_mandatory',
        'priority',
    )
    list_filter = ('is_mandatory', 'priority')
    search_fields = (
        'job_position__title',
        'function__name',
        'competency__name',
        'requirement__code',
        'requirement__title',
        'notes',
    )
    autocomplete_fields = ('job_position', 'function', 'competency', 'requirement')


@admin.register(TrainingSession)
class TrainingSessionAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = (
        'session_number',
        'requirement',
        'title',
        'delivery_method',
        'status',
        'scheduled_start',
        'instructor',
        'location_state_ref',
        'location_city_ref',
    )
    list_filter = (
        'delivery_method',
        'status',
        'scheduled_start',
        'location_state_ref',
        'location_city_ref',
    )
    search_fields = (
        'session_number',
        'title',
        'requirement__code',
        'requirement__title',
        'location',
        'location_city_ref__name',
        'location_state_ref__name',
        'notes',
    )
    autocomplete_fields = ('requirement', 'instructor', 'location_state_ref', 'location_city_ref')
    readonly_fields = ('session_number',)


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = (
        'enrollment_number',
        'requirement',
        'user',
        'status',
        'score',
        'valid_until',
        'certificate_number',
    )
    list_filter = ('status', 'due_date', 'valid_until', 'recertification_due_date')
    search_fields = (
        'enrollment_number',
        'requirement__code',
        'requirement__title',
        'user__email',
        'evidence_reference',
        'content_hash',
        'certificate_number',
        'certificate_reference',
    )
    autocomplete_fields = (
        'requirement',
        'session',
        'user',
        'convoked_by',
        'started_by',
        'completed_by',
        'approved_by',
        'revoked_by',
    )
    readonly_fields = (
        'enrollment_number',
        'started_at',
        'completed_at',
        'approved_at',
        'valid_until',
        'recertification_due_date',
        'certificate_number',
        'revoked_at',
        'is_valid',
    )


@admin.register(CriticalActivityRule)
class CriticalActivityRuleAdmin(GxpRetentionModelAdmin):
    list_display = (
        'activity_code',
        'name',
        'requirement',
        'enforcement_mode',
        'area',
        'process',
        'is_active',
    )
    list_filter = ('enforcement_mode', 'area', 'process', 'module_code', 'is_active')
    search_fields = (
        'activity_code',
        'name',
        'requirement__code',
        'requirement__title',
        'area',
        'process',
        'module_code',
        'notes',
    )
    autocomplete_fields = ('requirement',)


@admin.register(TrainingIndicatorReport)
class TrainingIndicatorReportAdmin(GxpRetentionModelAdmin):
    list_display = (
        'title',
        'report_type',
        'area',
        'process',
        'status',
        'total_required',
        'total_valid',
        'overdue_trainings',
        'compliance_rate',
    )
    list_filter = ('report_type', 'status', 'area', 'process', 'generated_at')
    search_fields = ('title', 'area', 'process', 'content_reference')
    autocomplete_fields = ('job_position', 'function', 'generated_by')
    readonly_fields = (
        'status',
        'total_required',
        'total_completed',
        'total_valid',
        'overdue_trainings',
        'due_soon_trainings',
        'compliance_rate',
        'content_reference',
        'generated_at',
    )
