from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db.models import F
from django.urls import reverse

from capa.models import CapaRecord
from deviations.models import QualityEvent
from training.models import TrainingEnrollment
from workflow.models import ApprovalTask, WorkflowNotification


@dataclass(frozen=True)
class PersonalAreaItem:
    identifier: int
    title: str
    subtitle: str
    url: str
    status_label: str
    due_date: date | datetime | None = None


@dataclass(frozen=True)
class PersonalAreaSection:
    key: str
    title: str
    icon: str
    items: tuple[PersonalAreaItem, ...]
    empty_message: str


SectionBuilder = Callable[[Any], PersonalAreaSection]


def _detail_url(module_slug: str, resource_slug: str, pk: int) -> str:
    return reverse('app:resource_detail', args=(module_slug, resource_slug, pk))


def _build_approvals(request: Any) -> PersonalAreaSection:
    tasks = (
        ApprovalTask.objects.filter(
            assigned_to=request.user,
            status=ApprovalTask.Status.PENDING,
        )
        .select_related('queue')
        .order_by(F('due_at').asc(nulls_last=True), '-created_at')[:10]
    )
    return PersonalAreaSection(
        key='approvals',
        title='Aprovações pendentes',
        icon='feather-check-square',
        items=tuple(
            PersonalAreaItem(
                identifier=task.pk,
                title=task.title,
                subtitle=task.queue.name,
                url=_detail_url('workflow', 'tasks', task.pk),
                status_label=task.get_status_display(),
                due_date=task.due_at,
            )
            for task in tasks
        ),
        empty_message='Nenhuma aprovação pendente para você.',
    )


def _build_notifications(request: Any) -> PersonalAreaSection:
    notifications = WorkflowNotification.objects.filter(
        recipient=request.user,
        status=WorkflowNotification.Status.UNREAD,
    ).order_by(F('due_at').asc(nulls_last=True), '-created_at')[:10]
    return PersonalAreaSection(
        key='notifications',
        title='Notificações não lidas',
        icon='feather-bell',
        items=tuple(
            PersonalAreaItem(
                identifier=notification.pk,
                title=notification.title,
                subtitle=notification.get_source_module_display(),
                url=_detail_url('workflow', 'notifications', notification.pk),
                status_label=notification.get_status_display(),
                due_date=notification.due_at,
            )
            for notification in notifications
        ),
        empty_message='Nenhuma notificação não lida.',
    )


def _build_deviations(request: Any) -> PersonalAreaSection:
    events = QualityEvent.objects.filter(
        responsible=request.user,
        status__in=(
            QualityEvent.Status.OPEN,
            QualityEvent.Status.UNDER_INVESTIGATION,
            QualityEvent.Status.PENDING_APPROVAL,
        ),
    ).order_by('-opened_at')[:10]
    return PersonalAreaSection(
        key='deviations',
        title='Desvios sob minha responsabilidade',
        icon='feather-alert-triangle',
        items=tuple(
            PersonalAreaItem(
                identifier=event.pk,
                title=event.event_number,
                subtitle=event.area,
                url=_detail_url('deviations', 'events', event.pk),
                status_label=event.get_status_display(),
            )
            for event in events
        ),
        empty_message='Nenhum desvio sob sua responsabilidade.',
    )


def _build_capas(request: Any) -> PersonalAreaSection:
    capas = (
        CapaRecord.objects.filter(owner=request.user)
        .exclude(status__in=(CapaRecord.Status.CLOSED, CapaRecord.Status.CANCELLED))
        .order_by('due_date', '-created_at')[:10]
    )
    return PersonalAreaSection(
        key='capas',
        title='CAPAs sob minha responsabilidade',
        icon='feather-target',
        items=tuple(
            PersonalAreaItem(
                identifier=capa.pk,
                title=capa.title,
                subtitle=capa.get_source_type_display(),
                url=_detail_url('capa', 'records', capa.pk),
                status_label=capa.get_status_display(),
                due_date=capa.due_date,
            )
            for capa in capas
        ),
        empty_message='Nenhuma CAPA sob sua responsabilidade.',
    )


def _build_training(request: Any) -> PersonalAreaSection:
    enrollments = (
        TrainingEnrollment.objects.filter(
            user=request.user,
            status__in=(
                TrainingEnrollment.Status.CONVOKED,
                TrainingEnrollment.Status.IN_PROGRESS,
                TrainingEnrollment.Status.FAILED,
                TrainingEnrollment.Status.EXPIRED,
            ),
        )
        .select_related('requirement', 'session')
        .order_by(F('due_date').asc(nulls_last=True), '-created_at')[:10]
    )
    return PersonalAreaSection(
        key='training',
        title='Treinamentos pendentes',
        icon='feather-user-check',
        items=tuple(
            PersonalAreaItem(
                identifier=enrollment.pk,
                title=enrollment.requirement.title,
                subtitle=enrollment.enrollment_number,
                url=_detail_url('training', 'enrollments', enrollment.pk),
                status_label=enrollment.get_status_display(),
                due_date=enrollment.due_date,
            )
            for enrollment in enrollments
        ),
        empty_message='Nenhum treinamento pendente.',
    )


PERSONAL_AREA_SECTIONS: tuple[tuple[str, SectionBuilder], ...] = (
    ('workflow.view_approvaltask', _build_approvals),
    ('workflow.view_workflownotification', _build_notifications),
    ('deviations.view_qualityevent', _build_deviations),
    ('capa.view_caparecord', _build_capas),
    ('training.view_trainingenrollment', _build_training),
)


def build_personal_area(request: Any) -> tuple[PersonalAreaSection, ...]:
    return tuple(
        builder(request)
        for permission, builder in PERSONAL_AREA_SECTIONS
        if request.user.has_perm(permission)
    )
