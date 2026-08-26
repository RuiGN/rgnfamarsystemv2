from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_client_uses_safe_text_rendering_and_persistent_session():
    script = (ROOT / 'static/js/rag-chat.js').read_text(encoding='utf-8')

    assert 'textContent = text' in script
    assert 'innerHTML' not in script
    assert 'sessionStorage.getItem' in script
    assert 'sessionStorage.setItem' in script
    assert 'sessionStorage.removeItem' in script
    assert 'data-rag-chat-retry' in script
    assert 'citation.url' in script
    assert 'citation.source_url' not in script


def test_dedicated_chat_does_not_advertise_mutating_tools():
    template = (ROOT / 'templates/app/resource_chat.html').read_text(encoding='utf-8')

    for forbidden in (
        'SQL Seguro ERP',
        'Gerar Relatório CAPA',
        'Propor Ishikawa',
        'ações diretas',
        'feather-paperclip',
    ):
        assert forbidden not in template


def test_global_widget_declares_one_endpoint_and_accessible_status():
    template = (ROOT / 'templates/includes/rag_chat.html').read_text(encoding='utf-8')

    assert template.count('data-rag-chat-endpoint=') == 1
    assert 'role="log"' in template
    assert 'data-rag-chat-status' in template
    assert 'maxlength="4000"' in template
