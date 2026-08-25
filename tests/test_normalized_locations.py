from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, migrations
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.utils import timezone

from auxiliary.models import City, StateProvince
from masters.models import BusinessPartner, Product, UnitOfMeasure


def create_state_city():
    state = StateProvince.objects.create(
        name='Pernambuco',
    )
    city = City.objects.create(
        name='Recife',
        state=state,
    )
    return state, city


@pytest.mark.django_db
def test_validate_normalized_location_checks_required_and_city_state_match():
    from base.normalized_locations import validate_normalized_location

    state, city = create_state_city()
    other_state = StateProvince.objects.create(name='São Paulo')

    class Holder:
        state_ref = other_state
        city_ref = city

    with pytest.raises(ValidationError) as error:
        validate_normalized_location(Holder(), require=True)

    assert 'city_ref' in error.value.message_dict

    class EmptyHolder:
        state_ref = None
        city_ref = None

    with pytest.raises(ValidationError) as missing_error:
        validate_normalized_location(EmptyHolder(), require=True)

    assert missing_error.value.message_dict == {
        'state_ref': ['Informe a UF.'],
        'city_ref': ['Informe a cidade.'],
    }


class PriorityNormalizedLocationTests(TestCase):
    def test_priority_serializers_expose_normalized_location_fields_only(self):
        from fiscal.serializers import FiscalCompanySerializer, FiscalMunicipalitySerializer
        from governance.serializers import InstitutionSettingsSerializer
        from masters.serializers import BusinessPartnerSerializer, SiteSerializer

        expectations = {
            FiscalCompanySerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
            FiscalMunicipalitySerializer: ({'state_ref', 'city_ref'}, {'state'}),
            InstitutionSettingsSerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
            BusinessPartnerSerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
            SiteSerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
        }

        for serializer_class, (required_fields, forbidden_fields) in expectations.items():
            fields = serializer_class().fields
            field_names = set(fields)
            assert required_fields <= field_names
            assert forbidden_fields.isdisjoint(field_names)
            for field_name in required_fields:
                expected_label = 'Cidade' if field_name.endswith('city_ref') else 'UF'
                assert fields[field_name].label == expected_label

    def test_priority_resource_registry_uses_normalized_location_fields_only(self):
        from base.ui.registry import get_resource

        expectations = {
            ('fiscal', 'companies'): {'state_ref', 'city_ref'},
            ('fiscal', 'municipalities'): {'state_ref', 'city_ref'},
            ('masters', 'partners'): {'state_ref', 'city_ref'},
            ('masters', 'sites'): {'state_ref', 'city_ref'},
            ('governance', 'institution-settings'): {'state_ref', 'city_ref'},
        }
        forbidden = {'state', 'city'}

        for resource_key, required_fields in expectations.items():
            resource = get_resource(*resource_key)
            list_fields = set(resource.list_display)
            form_fields = set(resource.form_fields or ())
            search_fields = set(resource.search_fields)

            assert required_fields <= list_fields | form_fields
            assert forbidden.isdisjoint(list_fields | form_fields)
            assert forbidden.isdisjoint({field.split('__', 1)[0] for field in search_fields})
            assert 'state_ref__name' in search_fields
            assert 'city_ref__name' in search_fields

    def test_fiscal_company_accepts_only_normalized_city_and_state_as_source(self):
        from fiscal.models import FiscalCompany

        state, city = create_state_city()
        company = FiscalCompany(
            legal_name='RGN Farma Recife',
            document='12.345.678/0001-90',
            tax_regime=FiscalCompany.TaxRegime.LUCRO_REAL,
            state_ref=state,
            city_ref=city,
        )

        company.full_clean()

    def test_fiscal_municipality_accepts_normalized_city_as_source(self):
        from fiscal.models import FiscalMunicipality

        state, city = create_state_city()
        municipality = FiscalMunicipality(
            ibge_code='2611606',
            state_ref=state,
            city_ref=city,
        )

        municipality.full_clean()

    def test_fiscal_municipality_serializer_persists_name_from_normalized_city(self):
        from fiscal.serializers import FiscalMunicipalitySerializer

        state, city = create_state_city()
        serializer = FiscalMunicipalitySerializer(
            data={
                'ibge_code': '2611606',
                'state_ref': state.pk,
                'city_ref': city.pk,
                'is_active': True,
            }
        )

        assert serializer.is_valid(), serializer.errors
        municipality = serializer.save()

        assert municipality.name == 'Recife'

    def test_priority_models_reject_city_from_different_state(self):
        from fiscal.models import FiscalCompany

        state, city = create_state_city()
        other_state = StateProvince.objects.create(
            name='São Paulo',
        )
        company = FiscalCompany(
            legal_name='RGN Farma Incoerente',
            document='12.345.678/0001-91',
            tax_regime=FiscalCompany.TaxRegime.LUCRO_REAL,
            state_ref=other_state,
            city_ref=city,
        )

        with pytest.raises(ValidationError) as error:
            company.full_clean()

        assert 'city_ref' in error.value.message_dict

    def test_fiscal_issue_payload_uses_normalized_location_not_legacy_text(self):
        from fiscal.models import (
            FiscalCompany,
            FiscalDocument,
            FiscalDocumentItem,
            FiscalNCM,
            FiscalOperationCode,
            FiscalTax,
            FiscalUnit,
            TaxSituation,
        )
        from fiscal.services import FiscalEmissionService

        state, city = create_state_city()
        unit = UnitOfMeasure.objects.create(name='Unidade', symbol='un')
        product = Product.objects.create(
            item_type=Product.ItemType.RAW_MATERIAL,
            unit=unit,
            status=Product.Status.APPROVED,
            fiscal_ncm='30049099',
        )
        partner = BusinessPartner.objects.create(
            legal_name='Cliente Normalizado',
            document='00000000000191',
            partner_type=BusinessPartner.PartnerType.CUSTOMER,
            qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
            qualification_valid_until=timezone.localdate().replace(
                year=timezone.localdate().year + 1
            ),
            state_ref=state,
            city_ref=city,
        )
        company = FiscalCompany.objects.create(
            legal_name='Empresa Normalizada',
            document='12.345.678/0001-90',
            tax_regime=FiscalCompany.TaxRegime.LUCRO_REAL,
            state_ref=state,
            city_ref=city,
        )
        fiscal_unit = FiscalUnit.objects.create(description='Unidade fiscal')
        ncm = FiscalNCM.objects.create(description='Medicamento')
        cfop = FiscalOperationCode.objects.create(
            direction=FiscalOperationCode.Direction.OUTBOUND,
        )
        tax_situation = TaxSituation.objects.create(
            tax_kind=TaxSituation.TaxKind.ICMS,
            regime_kind=TaxSituation.RegimeKind.CST,
        )
        document = FiscalDocument.objects.create(
            company=company,
            partner=partner,
            document_type=FiscalDocument.DocumentType.OUTBOUND,
            operation_type=FiscalDocument.OperationType.SALE,
            number='NF-NL',
            series='1',
            issue_date=timezone.localdate(),
            operation_date=timezone.localdate(),
        )
        item = FiscalDocumentItem.objects.create(
            document=document,
            line_number=1,
            product=product,
            fiscal_unit=fiscal_unit,
            ncm=ncm,
            cfop=cfop,
            tax_situation=tax_situation,
            quantity=Decimal('1.0000'),
            unit_price=Decimal('100.0000'),
        )
        FiscalTax.objects.create(
            document=document,
            item=item,
            tax_kind=FiscalTax.TaxKind.ICMS,
            base_amount=item.line_total,
            rate_percent=Decimal('18.0000'),
        )
        document.recalculate_totals()

        payload = FiscalEmissionService()._build_issue_payload(document)

        assert payload['company']['city'] == 'Recife'
        assert payload['company']['state'] == 'Pernambuco'
        assert payload['partner']['city'] == 'Recife'
        assert payload['partner']['state'] == 'Pernambuco'


class TransactionalNormalizedLocationTests(TestCase):
    def test_transactional_models_accept_normalized_location_references(self):
        from audits.models import AuditPlan, AuditProgram
        from crm.models import CustomerComplaint, SalesOrder
        from pharmacovigilance.models import PharmacovigilanceCase
        from procurement.models import PurchaseOrder, SupplierQualificationEvent
        from recalls.models import MarketComplaint
        from training.models import TrainingSession

        state, city = create_state_city()
        model_specs = (
            (
                AuditPlan,
                {
                    'venue_state_ref': state,
                    'venue_city_ref': city,
                },
            ),
            (
                SalesOrder,
                {
                    'shipping_state_ref': state,
                    'shipping_city_ref': city,
                },
            ),
            (
                CustomerComplaint,
                {
                    'state_ref': state,
                    'city_ref': city,
                },
            ),
            (
                PharmacovigilanceCase,
                {
                    'state_ref': state,
                    'city_ref': city,
                },
            ),
            (
                SupplierQualificationEvent,
                {
                    'event_state_ref': state,
                    'event_city_ref': city,
                },
            ),
            (
                PurchaseOrder,
                {
                    'delivery_state_ref': state,
                    'delivery_city_ref': city,
                },
            ),
            (
                MarketComplaint,
                {
                    'state_ref': state,
                    'city_ref': city,
                },
            ),
            (
                TrainingSession,
                {
                    'location_state_ref': state,
                    'location_city_ref': city,
                },
            ),
        )

        customer = BusinessPartner(
            legal_name='Cliente Normalizado',
            partner_type=BusinessPartner.PartnerType.CUSTOMER,
        )
        supplier = BusinessPartner(
            legal_name='Fornecedor Normalizado',
            partner_type=BusinessPartner.PartnerType.SUPPLIER,
        )
        related_fields = {
            SalesOrder: {'customer': customer},
            CustomerComplaint: {'customer': customer},
            PharmacovigilanceCase: {'customer': customer},
            SupplierQualificationEvent: {'supplier': supplier},
            PurchaseOrder: {'supplier': supplier},
            MarketComplaint: {'customer': customer},
        }

        for model, normalized_fields in model_specs:
            instance = model(**related_fields.get(model, {}), **normalized_fields)
            if model is AuditPlan:
                instance.program = AuditProgram()
            instance.full_clean(exclude=_required_fields_except_locations(model))

    def test_transactional_models_reject_mismatched_normalized_locations(self):
        from procurement.models import PurchaseOrder

        _state, city = create_state_city()
        other_state = StateProvince.objects.create(
            name='São Paulo',
        )
        order = PurchaseOrder(
            delivery_state_ref=other_state,
            delivery_city_ref=city,
        )

        with pytest.raises(ValidationError) as error:
            order.full_clean(exclude=_required_fields_except_locations(PurchaseOrder))

        assert 'delivery_city_ref' in error.value.message_dict

    def test_transactional_serializers_expose_normalized_location_fields_only(self):
        from audits.serializers import AuditPlanSerializer
        from crm.serializers import CustomerComplaintSerializer, SalesOrderSerializer
        from pharmacovigilance.serializers import PharmacovigilanceCaseSerializer
        from procurement.serializers import (
            PurchaseOrderSerializer,
            SupplierQualificationEventSerializer,
        )
        from recalls.serializers import MarketComplaintSerializer
        from training.serializers import TrainingSessionSerializer

        expectations = {
            AuditPlanSerializer: (
                {'venue_state_ref', 'venue_city_ref'},
                {'venue_state', 'venue_city'},
            ),
            SalesOrderSerializer: (
                {'shipping_state_ref', 'shipping_city_ref'},
                {'shipping_state', 'shipping_city'},
            ),
            CustomerComplaintSerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
            PharmacovigilanceCaseSerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
            SupplierQualificationEventSerializer: (
                {'event_state_ref', 'event_city_ref'},
                {'event_state', 'event_city'},
            ),
            PurchaseOrderSerializer: (
                {'delivery_state_ref', 'delivery_city_ref'},
                {'delivery_state', 'delivery_city'},
            ),
            MarketComplaintSerializer: ({'state_ref', 'city_ref'}, {'state', 'city'}),
            TrainingSessionSerializer: (
                {'location_state_ref', 'location_city_ref'},
                {'location_state', 'location_city'},
            ),
        }

        for serializer_class, (required_fields, forbidden_fields) in expectations.items():
            fields = serializer_class().fields
            field_names = set(fields)
            assert required_fields <= field_names
            assert forbidden_fields.isdisjoint(field_names)
            for field_name in required_fields:
                expected_label = 'Cidade' if field_name.endswith('city_ref') else 'UF'
                assert fields[field_name].label == expected_label

    def test_transactional_resource_registry_uses_normalized_location_fields_only(self):
        from base.ui.registry import get_resource

        expectations = {
            ('audits', 'plans'): (
                {'venue_state_ref', 'venue_city_ref'},
                {'venue_state', 'venue_city'},
            ),
            ('crm', 'orders'): (
                {'shipping_state_ref', 'shipping_city_ref'},
                {'shipping_state', 'shipping_city'},
            ),
            ('crm', 'complaints'): ({'state_ref', 'city_ref'}, {'state', 'city'}),
            ('pharmacovigilance', 'cases'): ({'state_ref', 'city_ref'}, {'state', 'city'}),
            ('procurement', 'supplier-qualification-events'): (
                {'event_state_ref', 'event_city_ref'},
                {'event_state', 'event_city'},
            ),
            ('procurement', 'orders'): (
                {'delivery_state_ref', 'delivery_city_ref'},
                {'delivery_state', 'delivery_city'},
            ),
            ('recalls', 'complaints'): ({'state_ref', 'city_ref'}, {'state', 'city'}),
            ('training', 'sessions'): (
                {'location_state_ref', 'location_city_ref'},
                {'location_state', 'location_city'},
            ),
        }

        for resource_key, (required_fields, forbidden_fields) in expectations.items():
            resource = get_resource(*resource_key)
            list_fields = set(resource.list_display)
            form_fields = set(resource.form_fields or ())
            search_fields = set(resource.search_fields)

            assert required_fields <= list_fields | form_fields
            assert forbidden_fields.isdisjoint(list_fields | form_fields)
            assert forbidden_fields.isdisjoint({field.split('__', 1)[0] for field in search_fields})
            assert any(field.endswith('__name') for field in search_fields)


def _required_fields_except_locations(model):
    location_fields = {
        'city',
        'state',
        'city_ref',
        'state_ref',
        'venue_city',
        'venue_state',
        'venue_city_ref',
        'venue_state_ref',
        'shipping_city',
        'shipping_state',
        'shipping_city_ref',
        'shipping_state_ref',
        'event_city',
        'event_state',
        'event_city_ref',
        'event_state_ref',
        'delivery_city',
        'delivery_state',
        'delivery_city_ref',
        'delivery_state_ref',
        'location_city',
        'location_state',
        'location_city_ref',
        'location_state_ref',
    }
    return [
        field.name
        for field in model._meta.fields
        if not field.blank and not field.null and field.name not in location_fields
    ]


def test_location_models_keep_only_normalized_city_and_uf_with_final_labels():
    expectations = (
        ('fiscal', 'FiscalCompany', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('fiscal', 'FiscalMunicipality', {'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        (
            'governance',
            'InstitutionSettings',
            {'city', 'state'},
            {'city_ref': 'Cidade', 'state_ref': 'UF'},
        ),
        (
            'masters',
            'BusinessPartner',
            {'city', 'state'},
            {'city_ref': 'Cidade', 'state_ref': 'UF'},
        ),
        ('masters', 'Site', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        (
            'audits',
            'AuditPlan',
            {'venue_city', 'venue_state'},
            {'venue_city_ref': 'Cidade', 'venue_state_ref': 'UF'},
        ),
        (
            'crm',
            'SalesOrder',
            {'shipping_city', 'shipping_state'},
            {'shipping_city_ref': 'Cidade', 'shipping_state_ref': 'UF'},
        ),
        ('crm', 'CustomerComplaint', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        (
            'pharmacovigilance',
            'PharmacovigilanceCase',
            {'city', 'state'},
            {'city_ref': 'Cidade', 'state_ref': 'UF'},
        ),
        (
            'procurement',
            'SupplierQualificationEvent',
            {'event_city', 'event_state'},
            {'event_city_ref': 'Cidade', 'event_state_ref': 'UF'},
        ),
        (
            'procurement',
            'PurchaseOrder',
            {'delivery_city', 'delivery_state'},
            {'delivery_city_ref': 'Cidade', 'delivery_state_ref': 'UF'},
        ),
        (
            'recalls',
            'MarketComplaint',
            {'city', 'state'},
            {'city_ref': 'Cidade', 'state_ref': 'UF'},
        ),
        (
            'training',
            'TrainingSession',
            {'location_city', 'location_state'},
            {'location_city_ref': 'Cidade', 'location_state_ref': 'UF'},
        ),
    )

    from django.apps import apps

    for app_label, model_name, removed_fields, normalized_labels in expectations:
        model = apps.get_model(app_label, model_name)
        model_fields = {field.name: field for field in model._meta.fields}
        assert removed_fields.isdisjoint(model_fields)
        for field_name, expected_label in normalized_labels.items():
            assert str(model_fields[field_name].verbose_name) == expected_label


def test_location_models_with_street_also_have_number_and_complement_fields():
    expectations = {
        'masters.BusinessPartner': {'street_number': 'número', 'complement': 'complemento'},
        'masters.Site': {'street_number': 'número', 'complement': 'complemento'},
        'audits.AuditPlan': {'venue_street_number': 'número', 'venue_complement': 'complemento'},
        'crm.SalesOrder': {
            'shipping_street_number': 'número',
            'shipping_complement': 'complemento',
        },
        'procurement.SupplierQualificationEvent': {
            'event_street_number': 'número',
            'event_complement': 'complemento',
        },
        'procurement.PurchaseOrder': {
            'delivery_street_number': 'número',
            'delivery_complement': 'complemento',
        },
        'training.TrainingSession': {
            'location_street_number': 'número',
            'location_complement': 'complemento',
        },
    }

    from django.apps import apps

    for model_path, expected_fields in expectations.items():
        app_label, model_name = model_path.split('.')
        model = apps.get_model(app_label, model_name)
        model_fields = {field.name: field for field in model._meta.fields}
        for field_name, expected_label in expected_fields.items():
            assert field_name in model_fields
            assert str(model_fields[field_name].verbose_name) == expected_label
            assert model_fields[field_name].blank is True


def test_affected_location_viewsets_filter_only_by_normalized_location_fields():
    from audits.views import AuditPlanViewSet
    from crm.views import CustomerComplaintViewSet, SalesOrderViewSet
    from fiscal.views import FiscalCompanyViewSet, FiscalMunicipalityViewSet
    from governance.views import InstitutionSettingsViewSet
    from masters.views import BusinessPartnerViewSet, SiteViewSet
    from pharmacovigilance.views import PharmacovigilanceCaseViewSet
    from procurement.views import PurchaseOrderViewSet, SupplierQualificationEventViewSet
    from recalls.views import MarketComplaintViewSet
    from training.views import TrainingSessionViewSet

    expectations = (
        (FiscalCompanyViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (FiscalMunicipalityViewSet, {'city_ref', 'state_ref'}, {'state'}),
        (InstitutionSettingsViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (BusinessPartnerViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (SiteViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (AuditPlanViewSet, {'venue_city_ref', 'venue_state_ref'}, {'venue_city', 'venue_state'}),
        (
            SalesOrderViewSet,
            {'shipping_city_ref', 'shipping_state_ref'},
            {'shipping_city', 'shipping_state'},
        ),
        (CustomerComplaintViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (PharmacovigilanceCaseViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (
            SupplierQualificationEventViewSet,
            {'event_city_ref', 'event_state_ref'},
            {'event_city', 'event_state'},
        ),
        (
            PurchaseOrderViewSet,
            {'delivery_city_ref', 'delivery_state_ref'},
            {'delivery_city', 'delivery_state'},
        ),
        (MarketComplaintViewSet, {'city_ref', 'state_ref'}, {'city', 'state'}),
        (
            TrainingSessionViewSet,
            {'location_city_ref', 'location_state_ref'},
            {'location_city', 'location_state'},
        ),
    )

    for viewset_class, required_fields, forbidden_fields in expectations:
        filterset_fields = set(viewset_class.filterset_fields)
        assert required_fields <= filterset_fields
        assert forbidden_fields.isdisjoint(filterset_fields)


def test_registered_location_admins_expose_only_normalized_location_fields():
    from django.contrib import admin
    from django.apps import apps

    def field_names(items):
        for item in items:
            if isinstance(item, str):
                yield item
            elif isinstance(item, (list, tuple)):
                yield from field_names(item)

    expectations = (
        ('fiscal', 'FiscalCompany', {'city_ref', 'state_ref'}, {'city', 'state'}),
        ('fiscal', 'FiscalMunicipality', {'city_ref', 'state_ref'}, {'state'}),
        ('governance', 'InstitutionSettings', {'city_ref', 'state_ref'}, {'city', 'state'}),
        ('masters', 'BusinessPartner', {'city_ref', 'state_ref'}, {'city', 'state'}),
        ('masters', 'Site', {'city_ref', 'state_ref'}, {'city', 'state'}),
        (
            'audits',
            'AuditPlan',
            {'venue_city_ref', 'venue_state_ref'},
            {'venue_city', 'venue_state'},
        ),
        (
            'crm',
            'SalesOrder',
            {'shipping_city_ref', 'shipping_state_ref'},
            {'shipping_city', 'shipping_state'},
        ),
        ('crm', 'CustomerComplaint', {'city_ref', 'state_ref'}, {'city', 'state'}),
        (
            'pharmacovigilance',
            'PharmacovigilanceCase',
            {'city_ref', 'state_ref'},
            {'city', 'state'},
        ),
        (
            'procurement',
            'SupplierQualificationEvent',
            {'event_city_ref', 'event_state_ref'},
            {'event_city', 'event_state'},
        ),
        (
            'procurement',
            'PurchaseOrder',
            {'delivery_city_ref', 'delivery_state_ref'},
            {'delivery_city', 'delivery_state'},
        ),
        ('recalls', 'MarketComplaint', {'city_ref', 'state_ref'}, {'city', 'state'}),
        (
            'training',
            'TrainingSession',
            {'location_city_ref', 'location_state_ref'},
            {'location_city', 'location_state'},
        ),
    )

    for app_label, model_name, required_fields, forbidden_fields in expectations:
        model = apps.get_model(app_label, model_name)
        model_admin = admin.site._registry.get(model)
        assert model_admin is not None

        fieldsets = model_admin.fieldsets or ()
        fieldset_fields = {
            field_name
            for _title, options in fieldsets
            for field_name in field_names(options.get('fields', ()))
        }
        surfaces = (
            set(model_admin.list_display),
            set(model_admin.list_filter),
            set(model_admin.search_fields),
            set(model_admin.autocomplete_fields),
            fieldset_fields,
        )
        surface_roots = {
            field.lstrip('^$=@-').split('__', 1)[0] for surface in surfaces for field in surface
        }
        assert forbidden_fields.isdisjoint(surface_roots)
        assert required_fields <= surface_roots
        for field_name in required_fields & surface_roots:
            field = model._meta.get_field(field_name)
            expected_label = 'Cidade' if field_name.endswith('city_ref') else 'UF'
            assert str(field.verbose_name) == expected_label


def test_location_reference_fields_are_preserved_on_city_and_technical_responsible():
    from governance.models import TechnicalResponsible

    city_fields = {field.name for field in City._meta.fields}
    responsible_fields = {field.name for field in TechnicalResponsible._meta.fields}

    assert 'state' in city_fields
    assert 'council_state' in responsible_fields


def test_models_without_street_do_not_receive_address_number_or_complement_fields():
    from django.apps import apps

    address_completion_fields = {
        'street_number',
        'complement',
        'venue_street_number',
        'venue_complement',
        'shipping_street_number',
        'shipping_complement',
        'event_street_number',
        'event_complement',
        'delivery_street_number',
        'delivery_complement',
        'location_street_number',
        'location_complement',
    }
    models_without_street = (
        ('fiscal', 'FiscalMunicipality'),
        ('crm', 'CustomerComplaint'),
        ('pharmacovigilance', 'PharmacovigilanceCase'),
        ('recalls', 'MarketComplaint'),
    )

    for app_label, model_name in models_without_street:
        model = apps.get_model(app_label, model_name)
        model_fields = {field.name for field in model._meta.fields}
        assert address_completion_fields.isdisjoint(model_fields)


@pytest.mark.django_db
def test_location_cleanup_migrations_guard_legacy_data_before_removing_columns():
    expected_removed_fields = {
        'fiscal': {'city', 'state'},
        'governance': {'city', 'state'},
        'masters': {'city', 'state'},
        'audits': {'venue_city', 'venue_state'},
        'crm': {'city', 'state', 'shipping_city', 'shipping_state'},
        'pharmacovigilance': {'city', 'state'},
        'procurement': {'event_city', 'event_state', 'delivery_city', 'delivery_state'},
        'recalls': {'city', 'state'},
        'training': {'location_city', 'location_state'},
    }
    loader = MigrationLoader(connection, ignore_no_migrations=True)

    guarded_apps = set()
    for (app_label, _migration_name), migration in loader.disk_migrations.items():
        if app_label not in expected_removed_fields:
            continue

        guard_seen = False
        for operation in migration.operations:
            if isinstance(operation, migrations.RunPython) and any(
                marker in getattr(operation.code, '__name__', '')
                for marker in ('validate_legacy_location', 'guard_legacy_location')
            ):
                guard_seen = True
                guarded_apps.add(app_label)

            if (
                isinstance(operation, migrations.RemoveField)
                and operation.name in expected_removed_fields[app_label]
            ):
                assert guard_seen, (
                    f'{app_label}.{migration.name} removes {operation.name} '
                    'before validating legacy location text against normalized FKs.'
                )

    assert guarded_apps == set(expected_removed_fields)
