from pathlib import Path
import subprocess

from masters.models import MasterCategory, Product


ROOT = Path(__file__).resolve().parents[1]


def test_product_model_does_not_expose_retired_route_taxonomy():
    retired_field = 'administration' + '_route'
    retired_kind = retired_field

    assert retired_field not in {field.name for field in Product._meta.fields}
    assert retired_kind not in MasterCategory.Kind.values


def test_product_model_does_not_expose_retired_application_area_taxonomy():
    retired_field = 'application' + '_area'
    retired_kind = retired_field

    assert retired_field not in {field.name for field in Product._meta.fields}
    assert retired_kind not in MasterCategory.Kind.values


def test_versioned_files_do_not_reference_retired_route_taxonomy():
    retired_terms = (
        b'administration' + b'_route',
        b'route' + b'_products',
        ('via de ' + 'administração').encode(),
        ('vias de ' + 'administração').encode(),
    )
    versioned = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b'\0')

    violations = []
    for relative_path in versioned:
        if not relative_path:
            continue
        path = ROOT / relative_path.decode()
        if not path.is_file():
            continue
        lowered_path = relative_path.lower()
        content = path.read_bytes().lower()
        if any(term in lowered_path or term in content for term in retired_terms):
            violations.append(relative_path.decode())

    assert violations == []
