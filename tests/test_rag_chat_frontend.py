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


def test_global_widget_uses_bootstrap_offcanvas_without_manual_visibility_control():
    template = (ROOT / 'templates/includes/rag_chat.html').read_text(encoding='utf-8')
    script = (ROOT / 'static/js/rag-chat.js').read_text(encoding='utf-8')

    assert 'data-bs-toggle="offcanvas"' in template
    assert 'data-bs-target="#rag-chat-panel"' in template
    assert 'class="offcanvas offcanvas-end rag-chat__panel"' in template
    assert 'data-bs-dismiss="offcanvas"' in template
    assert 'aria-labelledby="rag-chat-title"' in template
    assert 'shown.bs.offcanvas' in script
    assert 'hidden.bs.offcanvas' in script
    assert 'bootstrap.Offcanvas.getOrCreateInstance(panel)' in script
    assert 'offcanvas.show()' in script
    assert 'offcanvas.hide()' in script
    assert 'toggle.focus()' in script
    assert 'panel.hidden =' not in script
    assert 'function openPanel()' not in script
    assert 'function closePanel(' not in script
