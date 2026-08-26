from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_knowledge_runbook_documents_required_controls():
    content = (ROOT / 'docs/architecture/knowledge.md').read_text(encoding='utf-8')

    for required in (
        'knowledge.view_ragchatsession',
        'build_erp_manual_corpus',
        'rebuild_knowledge_index',
        'reconcile_knowledge_alias',
        'RAG_CHAT_LOCAL_ONLY',
        'fallback PostgreSQL',
        'somente leitura',
        'isolamento por usuário',
        'rollback',
    ):
        assert required in content
    assert 'sync_assistant_action_policies' not in content


def test_user_and_functional_docs_state_permission_and_read_only_scope():
    paths = (
        ROOT / 'README.md',
        ROOT / 'docs/pdf/especificacao_tecnica.md',
        ROOT / 'docs/pdf/especificacao_funcional.md',
        ROOT / 'docs/pdf/manual_usuario.md',
    )

    for path in paths:
        content = path.read_text(encoding='utf-8')
        assert 'knowledge.view_ragchatsession' in content, path
        assert 'somente leitura' in content, path
