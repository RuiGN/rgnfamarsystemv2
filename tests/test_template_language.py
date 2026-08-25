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
