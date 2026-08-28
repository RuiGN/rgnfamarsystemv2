from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from inventory.models import StockLot
from production.models import ProductionOrder
from quality.models import LaboratoryInvestigation, QualityAnalysis, QualitySample
from workflow.models import ApprovalTask, AsyncJobStatus, WorkflowNotification

from .registry import get_module


@dataclass(frozen=True)
class WorkspaceMetric:
    label: str
    value: int
    icon: str
    tone: str
    badge: str
    url: str
    required_permission: str = ''

    def can_view(self, user: Any) -> bool:
        return not self.required_permission or user.has_perm(self.required_permission)


@dataclass(frozen=True)
class WorkspaceLink:
    label: str
    icon: str
    url: str
    required_module_slug: str = ''

    def can_view(self, user: Any) -> bool:
        if not self.required_module_slug:
            return True
        module = get_module(self.required_module_slug)
        return module is not None and module.can_view(user)


@dataclass(frozen=True)
class WorkspaceContent:
    metrics: tuple[WorkspaceMetric, ...]
    quick_links: tuple[WorkspaceLink, ...]

    def visible_to(self, user: Any) -> 'WorkspaceContent':
        return WorkspaceContent(
            metrics=tuple(metric for metric in self.metrics if metric.can_view(user)),
            quick_links=tuple(link for link in self.quick_links if link.can_view(user)),
        )


@dataclass(frozen=True)
class WorkspaceConfig:
    slug: str
    title: str
    description: str
    breadcrumb_label: str
    module_slug: str
    quick_links_title: str
    builder: Callable[[Any], WorkspaceContent]

    def build_content(self, request: Any) -> WorkspaceContent:
        return self.builder(request).visible_to(request.user)


def _resource_url(module_slug: str, resource_slug: str) -> str:
    return reverse('app:resource_list', args=(module_slug, resource_slug))


def _module_url(module_slug: str) -> str:
    return reverse('app:module', args=(module_slug,))


def build_operations_content(request: Any) -> WorkspaceContent:
    del request
    return WorkspaceContent(
        metrics=(
            WorkspaceMetric(
                label='Ordens em execução',
                value=ProductionOrder.objects.filter(
                    status=ProductionOrder.Status.IN_PROGRESS
                ).count(),
                icon='feather-play-circle',
                tone='primary',
                badge='Produção',
                url=_resource_url('production', 'orders'),
                required_permission='production.view_productionorder',
            ),
            WorkspaceMetric(
                label='Lotes em estoque',
                value=StockLot.objects.count(),
                icon='feather-archive',
                tone='success',
                badge='Estoque',
                url=_resource_url('inventory', 'lots'),
                required_permission='inventory.view_stocklot',
            ),
            WorkspaceMetric(
                label='Amostras pendentes',
                value=QualitySample.objects.exclude(
                    status__in=(
                        QualitySample.Status.APPROVED,
                        QualitySample.Status.REJECTED,
                        QualitySample.Status.CANCELLED,
                    )
                ).count(),
                icon='feather-check-square',
                tone='warning',
                badge='Qualidade',
                url=_resource_url('quality', 'samples'),
                required_permission='quality.view_qualitysample',
            ),
        ),
        quick_links=(
            WorkspaceLink(
                label='Planejamento',
                icon='feather-calendar',
                url=_module_url('planning'),
                required_module_slug='planning',
            ),
            WorkspaceLink(
                label='Compras',
                icon='feather-shopping-cart',
                url=_module_url('procurement'),
                required_module_slug='procurement',
            ),
            WorkspaceLink(
                label='Qualidade',
                icon='feather-check-square',
                url=_module_url('quality'),
                required_module_slug='quality',
            ),
        ),
    )


def build_quality_content(request: Any) -> WorkspaceContent:
    del request
    return WorkspaceContent(
        metrics=(
            WorkspaceMetric(
                label='Amostras em análise',
                value=QualitySample.objects.filter(
                    status=QualitySample.Status.IN_ANALYSIS
                ).count(),
                icon='feather-droplet',
                tone='warning',
                badge='Amostragem',
                url=_resource_url('quality', 'samples'),
                required_permission='quality.view_qualitysample',
            ),
            WorkspaceMetric(
                label='Análises pendentes',
                value=QualityAnalysis.objects.filter(
                    status=QualityAnalysis.Status.PENDING
                ).count(),
                icon='feather-activity',
                tone='primary',
                badge='Laboratório',
                url=_resource_url('quality', 'analyses'),
                required_permission='quality.view_qualityanalysis',
            ),
            WorkspaceMetric(
                label='Investigações abertas',
                value=LaboratoryInvestigation.objects.exclude(
                    status__in=(
                        LaboratoryInvestigation.Status.CONCLUDED,
                        LaboratoryInvestigation.Status.CANCELLED,
                    )
                ).count(),
                icon='feather-alert-triangle',
                tone='danger',
                badge='Investigação',
                url=_resource_url('quality', 'investigations'),
                required_permission='quality.view_laboratoryinvestigation',
            ),
        ),
        quick_links=(
            WorkspaceLink(
                label='Garantia da qualidade',
                icon='feather-shield',
                url=_module_url('qa'),
                required_module_slug='qa',
            ),
            WorkspaceLink(
                label='Desvios',
                icon='feather-alert-circle',
                url=_module_url('deviations'),
                required_module_slug='deviations',
            ),
            WorkspaceLink(
                label='CAPA',
                icon='feather-target',
                url=_module_url('capa'),
                required_module_slug='capa',
            ),
            WorkspaceLink(
                label='Documentos',
                icon='feather-file-text',
                url=_module_url('documents'),
                required_module_slug='documents',
            ),
        ),
    )


def build_workflow_content(request: Any) -> WorkspaceContent:
    return WorkspaceContent(
        metrics=(
            WorkspaceMetric(
                label='Aprovações pendentes',
                value=ApprovalTask.objects.filter(status=ApprovalTask.Status.PENDING).count(),
                icon='feather-check-square',
                tone='warning',
                badge='Aprovações',
                url=_resource_url('workflow', 'tasks'),
                required_permission='workflow.view_approvaltask',
            ),
            WorkspaceMetric(
                label='Notificações não lidas',
                value=WorkflowNotification.objects.filter(
                    recipient=request.user,
                    status=WorkflowNotification.Status.UNREAD,
                ).count(),
                icon='feather-bell',
                tone='primary',
                badge='Avisos',
                url=_resource_url('workflow', 'notifications'),
                required_permission='workflow.view_workflownotification',
            ),
            WorkspaceMetric(
                label='Jobs em execução',
                value=AsyncJobStatus.objects.filter(
                    status__in=(AsyncJobStatus.Status.PENDING, AsyncJobStatus.Status.RUNNING)
                ).count(),
                icon='feather-loader',
                tone='info',
                badge='Processamento',
                url=_resource_url('workflow', 'async-jobs'),
                required_permission='workflow.view_asyncjobstatus',
            ),
        ),
        quick_links=(
            WorkspaceLink(
                label='Todos os recursos',
                icon='feather-git-pull-request',
                url=_module_url('workflow'),
                required_module_slug='workflow',
            ),
            WorkspaceLink(
                label='Compliance',
                icon='feather-shield',
                url=_module_url('compliance'),
                required_module_slug='compliance',
            ),
            WorkspaceLink(
                label='Governança',
                icon='feather-settings',
                url=_module_url('governance'),
                required_module_slug='governance',
            ),
        ),
    )


WORKSPACES = {
    'operations': WorkspaceConfig(
        slug='operations',
        title='Cockpit operacional',
        description='Produção, estoque e qualidade em um único contexto.',
        breadcrumb_label='Operação',
        module_slug='production',
        quick_links_title='Acessos rápidos',
        builder=build_operations_content,
    ),
    'quality': WorkspaceConfig(
        slug='quality',
        title='Cockpit de qualidade',
        description='Amostragem, análises e investigações sob controle.',
        breadcrumb_label='Qualidade',
        module_slug='quality',
        quick_links_title='Fluxos de qualidade',
        builder=build_quality_content,
    ),
    'workflow': WorkspaceConfig(
        slug='workflow',
        title='Central de workflow',
        description='Aprovações, notificações e processamento assíncrono.',
        breadcrumb_label='Fluxo de trabalho',
        module_slug='workflow',
        quick_links_title='Governança operacional',
        builder=build_workflow_content,
    ),
}


def get_workspace(slug: str) -> WorkspaceConfig | None:
    return WORKSPACES.get(slug)
