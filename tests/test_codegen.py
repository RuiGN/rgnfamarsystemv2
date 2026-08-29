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


def test_generate_code_bootstraps_from_highest_existing_suffix():
    from base.sequences import generate_code
    from masters.models import Product

    Product.objects.create(
        code='PRD-0042',
        description='Produto importado',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=_unit(),
    )

    assert generate_code(Product, 'PRD') == 'PRD-0043'


def test_auto_code_on_save_when_blank():
    from masters.models import Product

    p = Product.objects.create(
        description='Produto Teste', item_type=Product.ItemType.RAW_MATERIAL, unit=_unit()
    )
    assert p.code.startswith('PRD-')
    assert p.code != ''


def test_explicit_code_is_preserved():
    from masters.models import Product

    p = Product.objects.create(
        code='MEU-CODIGO', description='X', item_type=Product.ItemType.RAW_MATERIAL, unit=_unit()
    )
    assert p.code == 'MEU-CODIGO'


def test_generated_code_skips_numeric_code_inserted_after_counter_creation():
    from masters.models import Product

    unit = _unit()
    first = Product.objects.create(
        description='Produto automático inicial',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )
    first_number = int(first.code.rsplit('-', 1)[1])
    Product.objects.create(
        code=f'PRD-{first_number + 1:04d}',
        description='Produto importado',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )

    generated = Product.objects.create(
        description='Produto automático seguinte',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )

    assert int(generated.code.rsplit('-', 1)[1]) == first_number + 2


def test_generated_codes_are_sequential_and_unique():
    from masters.models import Product

    unit = _unit()
    c1 = Product.objects.create(
        description='A', item_type=Product.ItemType.RAW_MATERIAL, unit=unit
    ).code
    c2 = Product.objects.create(
        description='B', item_type=Product.ItemType.RAW_MATERIAL, unit=unit
    ).code
    assert c1 != c2
    n1, n2 = int(c1.split('-')[1]), int(c2.split('-')[1])
    assert n2 == n1 + 1


def test_deleted_generated_code_is_not_reused():
    from masters.models import Product

    unit = _unit()
    first = Product.objects.create(
        description='Produto inicial',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )
    removed = Product.objects.create(
        description='Produto removido',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )
    removed_number = int(removed.code.rsplit('-', 1)[1])
    removed.delete()

    replacement = Product.objects.create(
        description='Produto substituto',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )

    assert replacement.code != first.code
    assert int(replacement.code.rsplit('-', 1)[1]) == removed_number + 1


def test_deleted_daily_identifier_is_not_reused():
    from base.sequences import sequence_code
    from masters.models import Product

    unit = _unit()
    first_code = sequence_code(Product, 'code', 'LOT')
    Product.objects.create(
        code=first_code,
        description='Lote inicial',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )
    removed_code = sequence_code(Product, 'code', 'LOT')
    removed = Product.objects.create(
        code=removed_code,
        description='Lote removido',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=unit,
    )
    removed_number = int(removed_code.rsplit('-', 1)[1])
    removed.delete()

    replacement_code = sequence_code(Product, 'code', 'LOT')

    assert int(replacement_code.rsplit('-', 1)[1]) == removed_number + 1


def test_generated_code_is_persisted_when_save_uses_update_fields():
    from masters.models import Product

    product = Product.objects.create(
        code='LEGADO-TEMPORARIO',
        description='Produto legado',
        item_type=Product.ItemType.RAW_MATERIAL,
        unit=_unit(),
    )
    Product.objects.filter(pk=product.pk).update(code='')
    product.refresh_from_db()

    product.description = 'Produto legado atualizado'
    product.save(update_fields=['description', 'updated_at'])
    product.refresh_from_db()

    assert product.code.startswith('PRD-')
    assert product.code != ''


def test_generate_code_rejects_value_larger_than_field(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    from base.sequences import generate_code
    from masters.models import Product

    field = Product._meta.get_field('code')
    monkeypatch.setattr(field, 'max_length', 7)

    with pytest.raises(
        ImproperlyConfigured,
        match=r'masters\.Product\.code.*max_length=7',
    ):
        generate_code(Product, 'PRD')


def test_generate_code_rejects_empty_prefix():
    from django.core.exceptions import ImproperlyConfigured

    from base.sequences import generate_code
    from masters.models import Product

    with pytest.raises(ImproperlyConfigured, match='prefixo'):
        generate_code(Product, '  ')


def test_generate_code_rejects_nonpositive_width():
    from django.core.exceptions import ImproperlyConfigured

    from base.sequences import generate_code
    from masters.models import Product

    with pytest.raises(ImproperlyConfigured, match='largura'):
        generate_code(Product, 'PRD', width=0)


def test_sequence_code_rejects_prefix_that_differs_from_model_declaration():
    from django.core.exceptions import ImproperlyConfigured

    from base.sequences import sequence_code
    from procurement.models import PurchaseOrder

    with pytest.raises(ImproperlyConfigured, match='prefixo declarado'):
        sequence_code(PurchaseOrder, 'order_number', 'INCORRETO')
