from django.contrib import admin
from qa.models import (
    BatchRecordChecklistItem,
    CriticalActivityRule,
    LotRelease,
    QAReview,
    QualityBlock,
    TrainingRecord,
    TrainingRequirement,
)


@admin.register(QAReview)
class QAReviewAdmin(admin.ModelAdmin):
    list_display = ('review_number', 'review_type', 'title', 'status', 'approved_by', 'approved_at')
    list_filter = ('review_type', 'status', 'approved_at')
    search_fields = (
        'review_number',
        'title',
        'stock_lot__lot_number',
        'production_order__order_number',
        'quality_document__document_number',
        'packaging_record_reference',
        'deviation_reference',
        'capa_reference',
        'change_reference',
        'controlled_document_reference',
    )
    autocomplete_fields = (
        'stock_lot',
        'production_order',
        'quality_document',
        'submitted_by',
        'approved_by',
        'rejected_by',
    )
    readonly_fields = ('review_number', 'submitted_at', 'approved_at', 'rejected_at')


@admin.register(BatchRecordChecklistItem)
class BatchRecordChecklistItemAdmin(admin.ModelAdmin):
    list_display = (
        'review',
        'title',
        'status',
        'responsible',
        'due_date',
        'completed_by',
        'completed_at',
    )
    list_filter = ('status', 'due_date', 'completed_at')
    search_fields = (
        'review__review_number',
        'title',
        'comments',
        'evidence_reference',
        'responsible__email',
    )
    autocomplete_fields = ('review', 'responsible', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(LotRelease)
class LotReleaseAdmin(admin.ModelAdmin):
    list_display = (
        'release_number',
        'product',
        'stock_lot',
        'release_status',
        'released_by',
        'released_at',
    )
    list_filter = ('release_status', 'released_at', 'blocked_at')
    search_fields = (
        'release_number',
        'product__code',
        'product__description',
        'stock_lot__lot_number',
        'qa_review__review_number',
        'quality_document__document_number',
        'decision',
    )
    autocomplete_fields = (
        'product',
        'stock_lot',
        'qa_review',
        'quality_document',
        'production_order',
        'released_by',
        'rejected_by',
        'blocked_by',
        'unblocked_by',
    )
    readonly_fields = (
        'release_number',
        'release_status',
        'decision',
        'released_by',
        'released_at',
        'rejected_by',
        'rejected_at',
        'rejection_reason',
        'blocked_by',
        'blocked_at',
        'block_reason',
        'unblocked_by',
        'unblocked_at',
        'unblock_reason',
    )

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields += LotRelease.TARGET_FIELDS
        return fields


@admin.register(QualityBlock)
class QualityBlockAdmin(admin.ModelAdmin):
    list_display = (
        'block_number',
        'target_type',
        'status',
        'blocked_by',
        'blocked_at',
        'unblocked_by',
        'unblocked_at',
    )
    list_filter = ('target_type', 'status', 'blocked_at', 'unblocked_at')
    search_fields = (
        'block_number',
        'product__code',
        'stock_lot__lot_number',
        'supplier__legal_name',
        'quality_document__document_number',
        'equipment_reference',
        'process_reference',
        'document_reference',
        'reason',
    )
    autocomplete_fields = (
        'product',
        'stock_lot',
        'supplier',
        'quality_document',
        'blocked_by',
        'unblocked_by',
    )
    readonly_fields = ('block_number', 'blocked_at', 'unblocked_at')


@admin.register(TrainingRequirement)
class TrainingRequirementAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'title',
        'required_role',
        'area',
        'process',
        'is_mandatory',
        'is_active',
    )
    list_filter = ('is_active', 'is_mandatory', 'area', 'process')
    search_fields = (
        'code',
        'title',
        'document_reference',
        'required_role',
        'area',
        'process',
        'target_user__email',
    )
    autocomplete_fields = ('target_user',)


@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ('requirement', 'user', 'status', 'valid_until', 'trainer', 'completed_at')
    list_filter = ('status', 'valid_until', 'completed_at')
    search_fields = (
        'requirement__code',
        'requirement__title',
        'user__email',
        'trainer__email',
        'evidence_reference',
    )
    autocomplete_fields = ('requirement', 'user', 'trainer')
    readonly_fields = ('is_valid',)


@admin.register(CriticalActivityRule)
class CriticalActivityRuleAdmin(admin.ModelAdmin):
    list_display = (
        'activity_code',
        'name',
        'training_requirement',
        'enforce_training',
        'is_active',
    )
    list_filter = ('is_active', 'enforce_training', 'area', 'process')
    search_fields = (
        'activity_code',
        'name',
        'training_requirement__code',
        'required_role',
        'area',
        'process',
    )
    autocomplete_fields = ('training_requirement',)
