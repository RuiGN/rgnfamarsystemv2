from io import StringIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection

from auxiliary.cosmetics_seed import (
    AUXILIARY_CATALOG_MANIFEST,
    AUXILIARY_CATALOG_PAYLOAD,
    build_auxiliary_catalog_payload,
    seed_cosmetics_auxiliary_data,
)
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
from reference_data.manifest import payload_hash


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


def test_auxiliary_manifest_freezes_every_seeded_catalog_including_registry():
    payload = build_auxiliary_catalog_payload()

    assert payload == AUXILIARY_CATALOG_PAYLOAD
    assert set(payload) == {
        'auxiliary.BusinessArea',
        'auxiliary.BusinessProcess',
        'auxiliary.Department',
        'auxiliary.OrganizationalRole',
        'auxiliary.CommercialTerm',
        'auxiliary.ImpactLevel',
        'auxiliary.CatalogType',
        'auxiliary.CatalogValue',
        'auxiliary.SystemModule',
        'auxiliary.SystemModel',
    }
    expected_counts = {
        'auxiliary.BusinessArea': 14,
        'auxiliary.BusinessProcess': 24,
        'auxiliary.Department': 17,
        'auxiliary.OrganizationalRole': 17,
        'auxiliary.CommercialTerm': 12,
        'auxiliary.ImpactLevel': 16,
        'auxiliary.CatalogType': 7,
        'auxiliary.CatalogValue': 32,
        'auxiliary.SystemModule': 29,
        'auxiliary.SystemModel': 200,
    }
    assert AUXILIARY_CATALOG_MANIFEST.expected_counts == expected_counts
    assert {section: len(records) for section, records in payload.items()} == expected_counts
    assert AUXILIARY_CATALOG_MANIFEST.sha256 == payload_hash(payload)
    assert AUXILIARY_CATALOG_MANIFEST.sha256 == (
        '02aa1bc8e5fa77022a611079ea49d129eb12836c6490c3fb32c2e6412b5638c3'
    )
    assert [row[3] for row in payload['auxiliary.SystemModule']] == sorted(
        row[3] for row in payload['auxiliary.SystemModule']
    )
    assert [(row[4], row[5]) for row in payload['auxiliary.SystemModel']] == sorted(
        (row[4], row[5]) for row in payload['auxiliary.SystemModel']
    )
    assert AUXILIARY_CATALOG_MANIFEST.provenance
    assert AUXILIARY_CATALOG_MANIFEST.license_name
    assert AUXILIARY_CATALOG_MANIFEST.license_url.startswith('https://')


def test_auxiliary_seed_rejects_same_size_payload_mutation_before_any_write(monkeypatch):
    from auxiliary import cosmetics_seed

    changed = list(cosmetics_seed.BUSINESS_AREAS)
    code, name, _description = changed[0]
    changed[0] = (code, name, 'Descrição adulterada sem nova versão.')
    monkeypatch.setattr(cosmetics_seed, 'BUSINESS_AREAS', tuple(changed))
    writes = []

    def record_write(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            writes.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(record_write):
        with pytest.raises(ValidationError, match='SHA-256'):
            seed_cosmetics_auxiliary_data()

    assert writes == []


def test_auxiliary_seed_full_cleans_whole_payload_before_first_write(monkeypatch):
    original_full_clean = SystemModel.full_clean

    def reject_last_model(instance, *args, **kwargs):
        if instance.code == AUXILIARY_CATALOG_PAYLOAD['auxiliary.SystemModel'][-1][0]:
            raise ValidationError('Modelo final inválido na pré-validação.')
        return original_full_clean(instance, *args, **kwargs)

    monkeypatch.setattr(SystemModel, 'full_clean', reject_last_model)
    writes = []

    def record_write(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            writes.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(record_write):
        with pytest.raises(ValidationError, match='Modelo final inválido'):
            seed_cosmetics_auxiliary_data()

    assert writes == []


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
