from pathlib import Path

from django.conf import settings
from django.utils import timezone

from base.modules import OperationalModule
from compliance.models import ComplianceChecklistItem


MODULE_FILE_SLUGS = {
    OperationalModule.AI_AGENTS: 'ai_agents',
}

MODULE_API_SLUGS = {
    OperationalModule.AI_AGENTS: 'ai-agents',
}

MODULE_DOC_SLUGS = {
    OperationalModule.AI_AGENTS: 'ai-agents',
}


def evaluate_module_readiness(module, user=None, project_root=None):
    root = Path(project_root or settings.BASE_DIR)
    file_slug = MODULE_FILE_SLUGS.get(module, module)
    api_slug = MODULE_API_SLUGS.get(module, module)
    doc_slug = MODULE_DOC_SLUGS.get(module, module)

    checks = [
        _check(
            ComplianceChecklistItem.CheckType.SINGLE_INSTANCE_SCOPE,
            _file_contains(root / file_slug / 'models.py', 'SingleInstanceModel'),
            f'{file_slug}/models.py usa SingleInstanceModel no runtime.',
            f'{file_slug}/models.py nao evidencia SingleInstanceModel no runtime.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.PERMISSION,
            _file_contains(root / file_slug / 'views.py', 'SingleInstanceDjangoModelPermissions'),
            f'{file_slug}/views.py aplica permissoes Django nativas.',
            f'{file_slug}/views.py nao evidencia permissoes Django nativas.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.API,
            _file_contains(root / 'core' / 'urls.py', f'api/{api_slug}/')
            and _file_contains(root / 'core' / 'api_v1_urls.py', f'{api_slug}/'),
            f'Rotas /api/{api_slug}/ e /api/v1/{api_slug}/ registradas.',
            f'Rotas de API para {api_slug} nao foram encontradas.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.AUDIT,
            _file_contains(root / file_slug / 'models.py', 'GovernanceAuditLog')
            or _file_contains(root / file_slug / 'models.py', 'Audit')
            or _file_contains(root / file_slug / 'models.py', 'audit'),
            f'{file_slug}/models.py evidencia auditoria ou log funcional.',
            f'{file_slug}/models.py nao evidencia auditoria.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.STATUS_HISTORY,
            _file_contains(root / 'compliance' / 'models.py', 'RecordStatusHistory'),
            'Historico generico RecordStatusHistory disponivel.',
            'Historico generico RecordStatusHistory nao esta disponivel.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.TRANSACTION,
            _file_contains(root / file_slug / 'models.py', 'transaction.atomic')
            or _file_contains(root / 'compliance' / 'models.py', 'transaction.atomic'),
            f'Acoes criticas de {file_slug} possuem suporte transacional.',
            f'Nao ha evidencia de transacao para {file_slug}.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.PTBR_MESSAGES,
            _module_has_ptbr_messages(root, file_slug),
            f'{file_slug} possui mensagens funcionais em portugues brasileiro.',
            f'{file_slug} nao evidencia mensagens em portugues brasileiro.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.DOCS,
            (root / 'docs' / 'architecture' / f'{doc_slug}.md').exists(),
            f'docs/architecture/{doc_slug}.md existe.',
            f'docs/architecture/{doc_slug}.md nao existe.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.MENU,
            _operational_menu_contract(root, file_slug),
            f'Menu operacional registra {file_slug} com permissao Django nativa.',
            f'Menu operacional ou permissao Django nativa ausente para {file_slug}.',
        ),
        _check(
            ComplianceChecklistItem.CheckType.TESTS,
            (root / 'tests' / f'test_{file_slug}.py').exists(),
            f'tests/test_{file_slug}.py existe.',
            f'tests/test_{file_slug}.py nao existe.',
        ),
    ]

    items = []
    for check_type, passed, pass_evidence, fail_evidence in checks:
        item, _created = ComplianceChecklistItem.objects.update_or_create(
            source_module=module,
            check_type=check_type,
            defaults={
                'status': ComplianceChecklistItem.Status.PASS
                if passed
                else ComplianceChecklistItem.Status.FAIL,
                'evidence': pass_evidence if passed else fail_evidence,
                'checked_by': user,
                'checked_at': timezone.now(),
            },
        )
        items.append(item)
    return {
        'module': module,
        'passed': all(item.status == ComplianceChecklistItem.Status.PASS for item in items),
        'items': items,
    }


def _check(check_type, passed, pass_evidence, fail_evidence):
    return check_type, bool(passed), pass_evidence, fail_evidence


def _file_contains(path, text):
    try:
        return text in path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return False


def _operational_menu_contract(root, file_slug):
    registry = root / 'base' / 'ui' / 'registry.py'
    module_registered = _file_contains(registry, f"ModuleConfig(\n        '{file_slug}',")
    permission_enforced = _file_contains(registry, 'user.has_perm')
    return module_registered and permission_enforced


def _module_has_ptbr_messages(root, file_slug):
    markers = ('Informe', 'Somente', 'deve', 'obrigatorio', 'obrigatoria', 'nao pode', 'não pode')
    for name in ('models.py', 'serializers.py', 'views.py'):
        path = root / file_slug / name
        try:
            content = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            continue
        if any(marker in content for marker in markers):
            return True
    return False
