import pytest
from django.core.exceptions import ValidationError

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data
from auxiliary.models import Department, OrganizationalRole
from costing.models import CostElement
from crm.models import CustomerGroup, SalesChannel
from finance.models import FinancialCategory
from fiscal.models import FiscalNCM, FiscalOperationCode, FiscalUnit, TaxSituation
from inventory.models import StockLot, StockMovement
from masters.models import BusinessPartner, MasterCategory, Product, UnitOfMeasure
from reference_data.cosmetics_catalogs import (
    COSMETICS_CATALOG_MANIFEST,
    JOB_POSITIONS,
    WORK_FUNCTIONS,
)
from reference_data.loaders import apply_catalogs, catalog_model_counts, validate_catalogs
from training.models import Competency, JobPosition, WorkFunction


pytestmark = pytest.mark.django_db


def test_catalogs_create_real_pt_br_reference_data_without_transactions():
    seed_cosmetics_auxiliary_data()

    result = apply_catalogs()

    assert UnitOfMeasure.objects.get(code='UOM-KG').name == 'Kilograma'
    assert UnitOfMeasure.objects.get(code='UOM-ML').symbol == 'mL'
    assert MasterCategory.objects.get(code='CAT-COS-FORM-EMULSAO').name == 'Emulsão'
    assert CostElement.objects.get(code='CE-COS-NQ').name == 'Custo da não qualidade'
    assert SalesChannel.objects.get(code='SC-COS-ECOM').name == 'E-commerce'
    assert FinancialCategory.objects.get(code='FC-COS-CQ').name == 'Controle da Qualidade'
    assert Competency.objects.get(code='CPT-COS-BPF').name == 'Boas Práticas de Fabricação'
    assert FiscalUnit.objects.get(code='KG').description == 'Kilograma'
    assert FiscalOperationCode.objects.get(code='5101').direction == 'outbound'
    assert result['masters.UnitOfMeasure']['managed'] == 21
    assert Product.objects.count() == 0
    assert BusinessPartner.objects.count() == 0
    assert StockLot.objects.count() == 0
    assert StockMovement.objects.count() == 0


def test_catalogs_overwrite_managed_and_preserve_local_records():
    seed_cosmetics_auxiliary_data()
    UnitOfMeasure.objects.create(code='UOM-KG', name='Nome incorreto', symbol='x')
    UnitOfMeasure.objects.create(code='LOCAL-BOMBONA', name='Bombona local', symbol='bb')
    CustomerGroup.objects.create(code='CG-LOCAL', name='Grupo local')

    first_result = apply_catalogs()
    first_counts = catalog_model_counts()
    second_result = apply_catalogs()

    assert UnitOfMeasure.objects.get(code='UOM-KG').name == 'Kilograma'
    assert UnitOfMeasure.objects.get(code='LOCAL-BOMBONA').name == 'Bombona local'
    assert CustomerGroup.objects.get(code='CG-LOCAL').name == 'Grupo local'
    assert catalog_model_counts() == first_counts
    assert first_result['masters.UnitOfMeasure']['updated'] == 1
    assert second_result['masters.UnitOfMeasure']['unchanged'] == 21


def test_catalog_manifest_records_counts_sources_and_fiscal_boundary():
    seed_cosmetics_auxiliary_data()
    validate_catalogs()

    assert COSMETICS_CATALOG_MANIFEST.expected_counts == {
        'masters.UnitOfMeasure': 21,
        'masters.MasterCategory': 42,
        'costing.CostElement': 10,
        'crm.CustomerGroup': 5,
        'crm.SalesChannel': 5,
        'finance.ChartOfAccount': 12,
        'finance.FinancialCategory': 6,
        'training.JobPosition': 17,
        'training.WorkFunction': 17,
        'training.Competency': 11,
        'fiscal.FiscalUnit': 11,
        'fiscal.FiscalOperationCode': 12,
    }
    assert any('si_versao_final.pdf' in url for url in COSMETICS_CATALOG_MANIFEST.source_urls)
    assert any('anexo-ecf-cfop' in url for url in COSMETICS_CATALOG_MANIFEST.source_urls)
    assert any('SINIEF' in namespace for namespace in COSMETICS_CATALOG_MANIFEST.namespaces)
    assert any('análise fiscal' in namespace for namespace in COSMETICS_CATALOG_MANIFEST.namespaces)


def test_job_positions_and_functions_derive_from_all_organizational_roles():
    seed_cosmetics_auxiliary_data()
    apply_catalogs()

    role_names = set(OrganizationalRole.objects.values_list('name', flat=True))
    assert len(JOB_POSITIONS) == len(WORK_FUNCTIONS) == 17
    assert set(JobPosition.objects.values_list('title', flat=True)) == role_names
    assert set(WorkFunction.objects.values_list('name', flat=True)) == role_names
    assert not JobPosition.objects.filter(area_ref__isnull=True).exists()
    assert not JobPosition.objects.filter(department_ref__isnull=True).exists()
    assert not WorkFunction.objects.filter(area_ref__isnull=True).exists()
    assert not WorkFunction.objects.filter(process_ref__isnull=True).exists()


def test_validation_happens_before_any_catalog_write(monkeypatch):
    from reference_data import cosmetics_catalogs

    seed_cosmetics_auxiliary_data()
    monkeypatch.setattr(
        cosmetics_catalogs,
        'UNITS',
        (*cosmetics_catalogs.UNITS, cosmetics_catalogs.UNITS[0]),
    )

    with pytest.raises(ValidationError, match='duplicado'):
        apply_catalogs()

    assert UnitOfMeasure.objects.count() == 0


def test_missing_auxiliary_dependency_rolls_back_all_catalog_writes():
    seed_cosmetics_auxiliary_data()
    Department.objects.get(code='DEP-COS-LIB').delete()

    with pytest.raises(ValidationError, match='DEP-COS-LIB'):
        apply_catalogs()

    assert UnitOfMeasure.objects.count() == 0


def test_catalogs_do_not_create_tax_determination_records():
    seed_cosmetics_auxiliary_data()

    apply_catalogs()

    assert FiscalNCM.objects.count() == 0
    assert TaxSituation.objects.count() == 0


def test_catalogs_roll_back_when_a_late_record_fails_full_clean(monkeypatch):
    seed_cosmetics_auxiliary_data()
    original_full_clean = FiscalOperationCode.full_clean

    def reject_last_cfop(instance, *args, **kwargs):
        if instance.code == '6910':
            raise ValidationError('CFOP inválido no fim da carga.')
        return original_full_clean(instance, *args, **kwargs)

    monkeypatch.setattr(FiscalOperationCode, 'full_clean', reject_last_cfop)

    with pytest.raises(ValidationError, match='fim da carga'):
        apply_catalogs()

    assert all(count == 0 for count in catalog_model_counts().values())
