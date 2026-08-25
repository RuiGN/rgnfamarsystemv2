import pytest

pytestmark = pytest.mark.django_db


def _unit():
    from masters.models import UnitOfMeasure
    return UnitOfMeasure.objects.first() or UnitOfMeasure.objects.create(
        name='Unidade', symbol='un'
    )


def test_generate_code_returns_prefix_sequence():
    from base.sequences import generate_code
    from masters.models import Product

    code = generate_code(Product, 'PRD')
    assert code.startswith('PRD-')
    assert code[4:].isdigit()


def test_auto_code_on_save_when_blank():
    from masters.models import Product

    p = Product.objects.create(description='Produto Teste', item_type=Product.ItemType.RAW_MATERIAL, unit=_unit())
    assert p.code.startswith('PRD-')
    assert p.code != ''


def test_explicit_code_is_preserved():
    from masters.models import Product

    p = Product.objects.create(code='MEU-CODIGO', description='X', item_type=Product.ItemType.RAW_MATERIAL, unit=_unit())
    assert p.code == 'MEU-CODIGO'


def test_generated_codes_are_sequential_and_unique():
    from masters.models import Product

    unit = _unit()
    c1 = Product.objects.create(description='A', item_type=Product.ItemType.RAW_MATERIAL, unit=unit).code
    c2 = Product.objects.create(description='B', item_type=Product.ItemType.RAW_MATERIAL, unit=unit).code
    assert c1 != c2
    n1, n2 = int(c1.split('-')[1]), int(c2.split('-')[1])
    assert n2 == n1 + 1
