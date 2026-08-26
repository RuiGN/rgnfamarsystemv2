from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_templates_do_not_expose_core_english_labels_or_mojibake():
    forbidden = (
        'Sair / Logout',
        'Provider:',
        'Model:',
        'Copyright',
        '>Apps<',
        'title="Apps"',
        'aria-label="Apps"',
        '>Dashboards<',
        'title="Dashboards"',
        'aria-label="Dashboards"',
        '>Dashboard<',
        'Login |',
    )
    templates = sorted((ROOT / 'templates').rglob('*.html'))
    mojibake_markers = ('Ã£', 'Ã¡', 'Ã¢', 'Ã©', 'Ãª', 'Ã­', 'Ã³', 'Ã´', 'Ãµ', 'Ãº', 'Ã§')

    for template in templates:
        source = template.read_text()
        assert '�' not in source
        for marker in mojibake_markers:
            assert marker not in source, f'{marker!r} encontrado em {template}'
        for text in forbidden:
            assert text not in source, f'{text!r} encontrado em {template}'


def test_templates_do_not_render_decorative_input_icons():
    forbidden = (
        'field.field.rgn_icon',
        'resource-input-icon',
        'resource-input-group',
        'data-field-icon',
    )

    for template in sorted((ROOT / 'templates').rglob('*.html')):
        source = template.read_text()
        for marker in forbidden:
            assert marker not in source, f'{marker!r} encontrado em {template}'


def test_representative_functional_icons_remain_available():
    form_actions = (ROOT / 'templates/includes/form_actions.html').read_text()
    base = (ROOT / 'templates/base.html').read_text()
    chat = (ROOT / 'templates/app/resource_chat.html').read_text()

    assert 'feather-save' in form_actions
    assert 'feather-x' in form_actions
    assert 'feather-search' in base
    assert 'btn-close' in base
    assert 'feather-paperclip' in chat
    assert 'feather-send' in chat
