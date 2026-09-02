from io import StringIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data
from auxiliary.models import (
    BusinessArea,
    BusinessProcess,
    CatalogType,
    CatalogValue,
    CommercialTerm,
    Department,
    ImpactLevel,
    OrganizationalRole,
    SystemModel,
    SystemModule,
)
from masters.models import Product


pytestmark = pytest.mark.django_db


def _managed_counts():
    models = (
        BusinessArea,
        BusinessProcess,
        Department,
        OrganizationalRole,
        CommercialTerm,
        SystemModule,
        SystemModel,
        ImpactLevel,
        CatalogType,
        CatalogValue,
    )
    return {model._meta.label: model.objects.count() for model in models}


def test_seed_creates_linked_cosmetics_catalogs_only_in_auxiliary():
    product_count = Product.objects.count()

    result = seed_cosmetics_auxiliary_data()

    production = BusinessArea.objects.get(code='BA-COS-PROD')
    assert production.name == 'Produção'
    assert BusinessProcess.objects.get(code='BPC-COS-FAB').area == production
    assert Department.objects.get(code='DEP-COS-ENV').area == production
    engineering = BusinessArea.objects.get(code='BA-COS-ENG')
    quality_assurance = BusinessArea.objects.get(code='BA-COS-GQ')
    assert BusinessProcess.objects.get(code='BPC-COS-MAN').area == engineering
    assert BusinessProcess.objects.get(code='BPC-COS-AUD').area == quality_assurance
    assert Department.objects.get(code='DEP-COS-AUD').area == quality_assurance
    assert CommercialTerm.objects.get(code='CTM-COS-PG30').days == 30
    assert ImpactLevel.objects.get(code='IL-COS-RISK-4').name == 'Crítico'
    material_type = CatalogType.objects.get(code='CTG-COS-MATERIAL')
    assert CatalogValue.objects.get(code='CV-COS-MAT-MP').catalog_type == material_type
    assert SystemModule.objects.filter(app_label='auxiliary').exists()
    assert SystemModel.objects.filter(app_label='auxiliary', model_name='currency').exists()
    assert (
        result['business_areas'] == BusinessArea.objects.filter(code__startswith='BA-COS-').count()
    )
    assert result['business_processes'] == 24
    assert result['departments'] == 17
    assert Product.objects.count() == product_count


def test_seed_is_idempotent_and_preserves_unmanaged_records():
    BusinessArea.objects.create(code='BA-LOCAL', name='Área local')
    seed_cosmetics_auxiliary_data()
    first = _managed_counts()

    seed_cosmetics_auxiliary_data()

    assert _managed_counts() == first
    assert BusinessArea.objects.get(code='BA-LOCAL').name == 'Área local'


def test_seed_rolls_back_when_curated_record_is_invalid(monkeypatch):
    from auxiliary import cosmetics_seed

    monkeypatch.setattr(
        cosmetics_seed,
        'BUSINESS_AREAS',
        (*cosmetics_seed.BUSINESS_AREAS, ('BA-COS-INVALID', '', 'Inválido')),
    )

    with pytest.raises(ValidationError):
        seed_cosmetics_auxiliary_data()

    assert BusinessArea.objects.count() == 0


def test_command_can_run_official_references_before_cosmetics_catalog():
    stdout = StringIO()
    with patch(
        'auxiliary.management.commands.load_cosmetics_auxiliary_data.call_command'
    ) as nested_call:
        call_command(
            'load_cosmetics_auxiliary_data',
            with_official_references=True,
            stdout=stdout,
        )

    nested_call.assert_called_once_with('load_official_reference_data')
    assert 'Carga auxiliar cosmética concluída' in stdout.getvalue()
