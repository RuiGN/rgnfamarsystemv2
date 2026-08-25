from django.conf import settings
from django.db import OperationalError, ProgrammingError

from base.ui.registry import get_visible_modules
from governance.models import InstitutionSettings
from workflow.models import WorkflowNotification


DASHBOARD_NAVIGATION = (
    ('executive', 'Executivo', 'production'),
    ('operations', 'Operação e PCP', 'production'),
    ('inventory', 'Estoque', 'inventory'),
    ('quality', 'Qualidade', 'quality'),
    ('regulatory', 'Regulatório e GxP', 'regulatory'),
    ('finance', 'Financeiro', 'finance'),
)


def _institution_brand_context():
    try:
        institution = (
            InstitutionSettings.objects.filter(is_active=True)
            .order_by('-updated_at', '-created_at', '-pk')
            .first()
        )
    except (OperationalError, ProgrammingError):
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
        'rag_chat_local_only': getattr(settings, 'RAG_CHAT_LOCAL_ONLY', True),
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
    if not getattr(user, 'is_authenticated', False):
        return {
            'sidebar_modules': (),
            'dashboard_navigation': (),
            'sidebar_admin_links': (),
            'unread_workflow_notifications': 0,
            **navigation_context,
            **brand_context,
        }

    modules = get_visible_modules(user)
    visible_module_slugs = {module.slug for module in modules}
    unread_notifications = WorkflowNotification.objects.filter(
        recipient=user,
        status=WorkflowNotification.Status.UNREAD,
    ).count()
    return {
        'sidebar_modules': modules,
        'dashboard_navigation': tuple(
            (slug, label)
            for slug, label, module_slug in DASHBOARD_NAVIGATION
            if module_slug in visible_module_slugs
        ),
        'sidebar_admin_links': (),
        'unread_workflow_notifications': unread_notifications,
        **navigation_context,
        **brand_context,
    }
