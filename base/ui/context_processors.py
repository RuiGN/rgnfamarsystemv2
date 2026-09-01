from django.db import OperationalError, ProgrammingError

from base.ui.registry import get_visible_modules
from base.ui.presentation import NotificationPreview
from base.ui.workspaces import WORKSPACES
from governance.models import InstitutionSettings
from workflow.models import WorkflowNotification


DASHBOARD_NAVIGATION = (
    ('executive', 'Executivo', 'production'),
    ('operations', 'Operação e PCP', 'production'),
    ('inventory', 'Estoque', 'inventory'),
    ('quality', 'Qualidade', 'quality'),
    ('finance', 'Financeiro', 'finance'),
)

SIDEBAR_DOMAINS = (
    (
        'operations',
        'Operações',
        ('formulations', 'production', 'planning', 'inventory'),
    ),
    (
        'quality',
        'Qualidade',
        ('quality', 'qa', 'deviations', 'capa', 'changes', 'audits', 'risks', 'recalls'),
    ),
    ('supply', 'Suprimentos', ('procurement',)),
    ('commercial', 'Comercial', ('crm',)),
    ('finance', 'Financeiro e fiscal', ('costing', 'finance', 'fiscal')),
    (
        'compliance',
        'Governança e conformidade',
        ('documents', 'training', 'files', 'workflow', 'reports', 'governance', 'compliance'),
    ),
    ('technology', 'Tecnologia', ('integrations', 'ai_agents', 'knowledge')),
    ('administration', 'Administração', ('masters', 'auxiliary')),
)


def group_sidebar_modules(modules):
    modules_by_slug = {module.slug: module for module in modules}
    grouped = []
    classified = set()
    for key, label, slugs in SIDEBAR_DOMAINS:
        domain_modules = tuple(
            modules_by_slug[slug]
            for slug in slugs
            if slug in modules_by_slug and slug not in classified
        )
        if domain_modules:
            grouped.append((key, label, domain_modules))
            classified.update(module.slug for module in domain_modules)

    other_modules = tuple(module for module in modules if module.slug not in classified)
    if other_modules:
        grouped.append(('other', 'Outros', other_modules))
    return tuple(grouped)


def _institution_brand_context():
    try:
        institution = (
            InstitutionSettings.objects.filter(is_active=True)
            .order_by('-updated_at', '-created_at', '-pk')
            .first()
        )
    except OperationalError, ProgrammingError:
        institution = None

    logo_url = ''
    if institution and institution.logo:
        try:
            logo_url = institution.logo.url
        except ValueError:
            logo_url = ''

    return {
        'active_institution': institution,
        'institution_name': str(institution) if institution else 'RGN Farma System',
        'institution_logo_url': logo_url,
    }


def sidebar_menu(request):
    user = getattr(request, 'user', None)
    resolver_match = getattr(request, 'resolver_match', None)
    route_kwargs = getattr(resolver_match, 'kwargs', {}) if resolver_match else {}
    navigation_context = {
        'active_module_slug': route_kwargs.get('module_slug', ''),
        'active_resource_slug': route_kwargs.get('resource_slug', ''),
    }
    brand_context = _institution_brand_context()
    if user is None or not getattr(user, 'is_authenticated', False):
        return {
            'sidebar_modules': (),
            'sidebar_domains': (),
            'sidebar_workspaces': (),
            'dashboard_navigation': (),
            'show_dashboard_navigation': False,
            'can_view_workflow_workspace': False,
            'can_preview_workflow_notifications': False,
            'sidebar_admin_links': (),
            'unread_workflow_notifications': 0,
            'workflow_notification_previews': (),
            **navigation_context,
            **brand_context,
        }
    modules = get_visible_modules(user)
    sidebar_domains = group_sidebar_modules(modules)
    visible_module_slugs = {module.slug for module in modules}
    sidebar_workspaces = tuple(
        sorted(
            (
                workspace
                for workspace in WORKSPACES.values()
                if workspace.module_slug in visible_module_slugs
            ),
            key=lambda workspace: workspace.order,
        )
    )
    dashboard_navigation = tuple(
        (slug, label)
        for slug, label, module_slug in DASHBOARD_NAVIGATION
        if module_slug in visible_module_slugs
    )
    can_view_workflow_workspace = any(
        workspace.slug == 'workflow' for workspace in sidebar_workspaces
    )
    can_preview_workflow_notifications = can_view_workflow_workspace and user.has_perm(
        'workflow.view_workflownotification'
    )
    workflow_notification_previews: tuple[NotificationPreview, ...] = ()
    unread_notifications = 0
    if can_preview_workflow_notifications:
        notifications = WorkflowNotification.objects.filter(recipient=user).order_by('-created_at')[
            :5
        ]
        workflow_notification_previews = tuple(
            NotificationPreview.from_model(notification) for notification in notifications
        )
        unread_notifications = WorkflowNotification.objects.filter(
            recipient=user,
            status=WorkflowNotification.Status.UNREAD,
        ).count()

    return {
        'sidebar_modules': modules,
        'sidebar_domains': sidebar_domains,
        'sidebar_workspaces': sidebar_workspaces,
        'dashboard_navigation': dashboard_navigation,
        'show_dashboard_navigation': bool(dashboard_navigation),
        'can_view_workflow_workspace': can_view_workflow_workspace,
        'can_preview_workflow_notifications': can_preview_workflow_notifications,
        'sidebar_admin_links': (),
        'unread_workflow_notifications': unread_notifications,
        'workflow_notification_previews': workflow_notification_previews,
        **navigation_context,
        **brand_context,
    }
