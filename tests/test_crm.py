from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from auxiliary.models import City, StateProvince
from inventory.models import StockBalance, StockLot, StockQualityStatus
from masters.models import BusinessPartner, Product, Site, StorageLocation, UnitOfMeasure, Warehouse


User = get_user_model()


def create_customer_product_stock(suffix='001', stock_quantity=Decimal('100.0000')):
    unit = UnitOfMeasure.objects.create(
        code=f'UN-{suffix}',
        name='Unidade',
        symbol='un',
    )
    product = Product.objects.create(
        code=f'PA-{suffix}',
        description=f'Produto acabado {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    customer = BusinessPartner.objects.create(
        code=f'CLI-{suffix}',
        legal_name=f'Cliente {suffix}',
        partner_type=BusinessPartner.PartnerType.CUSTOMER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
        document=f'00000000000{suffix}',
    )
    site = Site.objects.create(
        code=f'PL-{suffix}',
        name=f'Planta {suffix}',
        site_type=Site.SiteType.DISTRIBUTION,
    )
    warehouse = Warehouse.objects.create(
        site=site,
        code=f'EXP-{suffix}',
        name=f'Expedição {suffix}',
        warehouse_type=Warehouse.WarehouseType.FINISHED_PRODUCT,
    )
    location = StorageLocation.objects.create(
        warehouse=warehouse,
        code=f'END-{suffix}',
        name=f'Endereço {suffix}',
    )
    lot = StockLot.objects.create(
        product=product,
        lot_number=f'LOTE-{suffix}',
        quality_status=StockQualityStatus.APPROVED,
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    StockBalance.objects.create(
        product=product,
        lot=lot,
        warehouse=warehouse,
        location=location,
        quality_status=StockQualityStatus.APPROVED,
        quantity=stock_quantity,
        unit=unit,
    )
    return unit, product, customer, lot


def create_crm_setup(customer, suffix='001', credit_limit=Decimal('5000.0000')):
    from crm.models import (
        CustomerContact,
        CustomerGroup,
        CustomerProfile,
        SalesChannel,
        SalesRepresentative,
    )

    group = CustomerGroup.objects.create(
        code=f'GRP-{suffix}',
        name=f'Grupo econômico {suffix}',
    )
    channel = SalesChannel.objects.create(
        code=f'CAN-{suffix}',
        name=f'Canal {suffix}',
        channel_type=SalesChannel.ChannelType.DIRECT,
    )
    representative = SalesRepresentative.objects.create(
        code=f'REP-{suffix}',
        name=f'Representante {suffix}',
        email=f'rep{suffix}@example.com',
        commission_percent=Decimal('5.0000'),
    )
    profile = CustomerProfile.objects.create(
        customer=customer,
        group=group,
        default_channel=channel,
        representative=representative,
        credit_limit=credit_limit,
        payment_terms_days=30,
        price_list_code=f'TAB-{suffix}',
    )
    contact = CustomerContact.objects.create(
        customer=customer,
        name=f'Contato {suffix}',
        role='Compras',
        email=f'compras{suffix}@example.com',
        is_primary=True,
    )
    return group, channel, representative, profile, contact


def create_fiscal_document(customer, suffix='001'):
    from fiscal.models import FiscalCompany, FiscalDocument

    state = StateProvince.objects.create(
        name=f'Pernambuco CRM {suffix}',
    )
    city = City.objects.create(
        name='Recife',
        state=state,
    )
    company = FiscalCompany.objects.create(
        legal_name=f'RGN Farma {suffix}',
        document=f'12345678000{suffix}',
        tax_regime=FiscalCompany.TaxRegime.LUCRO_PRESUMIDO,
        state_ref=state,
        city_ref=city,
    )
    return FiscalDocument.objects.create(
        company=company,
        partner=customer,
        document_type=FiscalDocument.DocumentType.OUTBOUND,
        operation_type=FiscalDocument.OperationType.SALE,
        number=f'NF-{suffix}',
        series='1',
        issue_date=timezone.localdate(),
        operation_date=timezone.localdate(),
    )


class CrmModelTests(TestCase):
    def test_customer_profile_contacts_and_representative_validate_customer_context(self):
        from crm.models import CustomerProfile

        _unit, _product, customer, _lot = create_customer_product_stock()
        _group, _channel, representative, profile, contact = create_crm_setup(customer)
        _other_unit, _other_product, other_customer, _other_lot = create_customer_product_stock(
            suffix='999'
        )

        invalid_profile = CustomerProfile(
            customer=other_customer,
            credit_limit=Decimal('1000.0000'),
        )

        invalid_profile.full_clean()

        assert profile.customer == customer
        assert profile.credit_limit == Decimal('5000.0000')
        assert contact.is_primary is True
        assert representative.commission_percent == Decimal('5.0000')

    def test_opportunity_pipeline_proposal_contract_and_campaign_history(self):
        from crm.models import (
            Campaign,
            Opportunity,
            SalesContract,
            SalesProposal,
            SalesProposalItem,
        )

        user = User.objects.create_user(
            username='comercial@example.com',
            email='comercial@example.com',
            password='S3curePass!123',
        )
        _unit, product, customer, _lot = create_customer_product_stock()
        _group, channel, representative, _profile, contact = create_crm_setup(customer)
        campaign = Campaign.objects.create(
            name='Lançamento linha hospitalar',
            channel=channel,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=Campaign.Status.ACTIVE,
        )
        opportunity = Opportunity.objects.create(
            customer=customer,
            contact=contact,
            channel=channel,
            representative=representative,
            campaign=campaign,
            title='Fornecimento hospitalar trimestral',
            estimated_amount=Decimal('12000.0000'),
            probability_percent=Decimal('60.0000'),
        )
        opportunity.advance_to(Opportunity.Stage.PROPOSAL)
        proposal = SalesProposal.objects.create(
            opportunity=opportunity,
            customer=customer,
            valid_until=timezone.localdate() + timedelta(days=15),
        )
        SalesProposalItem.objects.create(
            proposal=proposal,
            product=product,
            quantity=Decimal('10.0000'),
            unit_price=Decimal('100.0000'),
            discount_percent=Decimal('5.0000'),
        )

        proposal.recalculate_total()
        proposal.send()
        proposal.accept()
        opportunity.mark_won()
        contract = SalesContract.objects.create(
            contract_number='CTR-001',
            customer=customer,
            opportunity=opportunity,
            proposal=proposal,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=365),
            contract_value=proposal.total_amount,
            payment_terms_days=30,
        )
        contract.activate(user=user)

        assert opportunity.stage == Opportunity.Stage.WON
        assert proposal.total_amount == Decimal('950.0000')
        assert proposal.status == SalesProposal.Status.ACCEPTED
        assert contract.status == SalesContract.Status.ACTIVE
        assert contract.approved_by == user

    def test_sales_order_approval_validates_credit_stock_payment_terms_and_regulatory_hold(self):
        from crm.models import CustomerProfile, SalesOrder, SalesOrderItem

        user = User.objects.create_user(
            username='vendas@example.com', email='vendas@example.com', password='S3curePass!123'
        )
        _unit, product, customer, _lot = create_customer_product_stock(
            stock_quantity=Decimal('20.0000')
        )
        _group, channel, representative, profile, _contact = create_crm_setup(
            customer,
            credit_limit=Decimal('2000.0000'),
        )
        order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            representative=representative,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('10.0000'),
            unit_price=Decimal('100.0000'),
        )

        order.approve(user=user)

        assert order.status == SalesOrder.Status.APPROVED
        assert order.total_amount == Decimal('1000.0000')
        assert order.approved_by == user

        profile.regulatory_hold = True
        profile.save(update_fields=['regulatory_hold', 'updated_at'])
        blocked_order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=blocked_order,
            product=product,
            quantity=Decimal('1.0000'),
            unit_price=Decimal('100.0000'),
        )

        with pytest.raises(ValidationError) as error:
            blocked_order.approve(user=user)

        blocked_order.refresh_from_db()
        assert blocked_order.status == SalesOrder.Status.BLOCKED
        assert 'regulatory_hold' in error.value.message_dict

        profile.regulatory_hold = False
        profile.save(update_fields=['regulatory_hold', 'updated_at'])
        out_of_stock_order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=out_of_stock_order,
            product=product,
            quantity=Decimal('999.0000'),
            unit_price=Decimal('100.0000'),
        )

        with pytest.raises(ValidationError) as error:
            out_of_stock_order.approve(user=user)

        assert 'stock' in error.value.message_dict

        profile.credit_limit = Decimal('500.0000')
        profile.save(update_fields=['credit_limit', 'updated_at'])
        credit_order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=credit_order,
            product=product,
            quantity=Decimal('6.0000'),
            unit_price=Decimal('100.0000'),
        )

        with pytest.raises(ValidationError) as error:
            credit_order.approve(user=user)

        assert 'credit_limit' in error.value.message_dict

        CustomerProfile.objects.filter(pk=profile.pk).update(
            credit_limit=Decimal('5000.0000'), payment_terms_days=15
        )
        term_order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=term_order,
            product=product,
            quantity=Decimal('1.0000'),
            unit_price=Decimal('100.0000'),
        )

        with pytest.raises(ValidationError) as error:
            term_order.approve(user=user)

        assert 'payment_terms_days' in error.value.message_dict

    def test_customer_interaction_records_history_for_opportunity(self):
        from crm.models import CustomerInteraction, Opportunity

        user = User.objects.create_user(
            username='atendimento@example.com',
            email='atendimento@example.com',
            password='S3curePass!123',
        )
        _unit, _product, customer, _lot = create_customer_product_stock()
        _group, channel, representative, _profile, contact = create_crm_setup(customer)
        opportunity = Opportunity.objects.create(
            customer=customer,
            contact=contact,
            channel=channel,
            representative=representative,
            title='Renovação de fornecimento',
        )

        interaction = CustomerInteraction.objects.create(
            customer=customer,
            contact=contact,
            opportunity=opportunity,
            interaction_type=CustomerInteraction.InteractionType.EMAIL,
            occurred_at=timezone.now(),
            subject='Follow-up de proposta',
            created_by=user,
        )

        assert interaction.opportunity == opportunity
        assert interaction.created_by == user
        assert interaction.interaction_type == CustomerInteraction.InteractionType.EMAIL

    def test_customer_complaint_links_lot_product_order_fiscal_document_quality_and_capa(self):
        from crm.models import CustomerComplaint, SalesOrder, SalesOrderItem

        user = User.objects.create_user(
            username='sac@example.com', email='sac@example.com', password='S3curePass!123'
        )
        _unit, product, customer, lot = create_customer_product_stock()
        _group, channel, representative, _profile, contact = create_crm_setup(customer)
        fiscal_document = create_fiscal_document(customer)
        order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            representative=representative,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('2.0000'),
            unit_price=Decimal('100.0000'),
        )
        order.approve(user=user)
        complaint = CustomerComplaint.objects.create(
            customer=customer,
            contact=contact,
            product=product,
            stock_lot=lot,
            sales_order=order,
            fiscal_document=fiscal_document,
            quality_reference='DEV-2026-001',
            capa_reference='CAPA-2026-001',
            severity=CustomerComplaint.Severity.HIGH,
            description='Reclamação de qualidade vinculada ao lote e aos documentos rastreáveis.',
        )

        complaint.start_investigation()
        complaint.close(resolution='Reposição aprovada e CAPA aberta.', user=user)

        assert complaint.status == CustomerComplaint.Status.CLOSED
        assert complaint.closed_by == user
        assert complaint.stock_lot == lot
        assert complaint.sales_order == order
        assert complaint.fiscal_document == fiscal_document


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestCrmApi:
    def test_customer_profile_api_uses_global_scope(self):
        from crm.models import CustomerProfile

        _unit, _product, customer, _lot = create_customer_product_stock()
        _other_unit, _other_product, other_customer, _other_lot = create_customer_product_stock(
            suffix='999'
        )
        create_crm_setup(other_customer, suffix='999')
        group, channel, representative, profile, _contact = create_crm_setup(customer)
        profile.delete()
        user = User.objects.create_user(
            username='crm.api@example.com', email='crm.api@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.force_authenticate(user)

        response = client.post(
            '/api/crm/customer-profiles/',
            {
                'customer': customer.id,
                'group': group.id,
                'default_channel': channel.id,
                'representative': representative.id,
                'credit_limit': '15000.0000',
                'payment_terms_days': 45,
                'price_list_code': 'TAB-HOSP',
            },
        )
        list_response = client.get('/api/crm/customer-profiles/')

        assert response.status_code == 201
        assert 'tenant' not in response.json()
        assert not hasattr(CustomerProfile.objects.get(pk=response.json()['id']), 'tenant')
        assert {item['customer'] for item in list_response.json()['results']} == {
            customer.id,
            other_customer.id,
        }

    def test_sales_order_api_approves_and_accepts_global_related_objects(self):
        from crm.models import SalesChannel, SalesOrder, SalesOrderItem

        _unit, product, customer, _lot = create_customer_product_stock()
        _other_unit, _other_product, _other_customer, _other_lot = create_customer_product_stock(
            suffix='999'
        )
        _group, channel, representative, _profile, _contact = create_crm_setup(customer)
        other_channel = SalesChannel.objects.create(
            name='Canal global secundário',
            channel_type=SalesChannel.ChannelType.DIRECT,
        )
        order = SalesOrder.objects.create(
            customer=customer,
            channel=channel,
            representative=representative,
            requested_delivery_date=timezone.localdate() + timedelta(days=7),
            payment_terms_days=30,
        )
        SalesOrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('5.0000'),
            unit_price=Decimal('100.0000'),
        )
        user = User.objects.create_user(
            username='vendas.api@example.com',
            email='vendas.api@example.com',
            password='S3curePass!123',
        )
        client = APIClient()
        client.force_authenticate(user)

        invalid_response = client.post(
            '/api/crm/orders/',
            {
                'customer': customer.id,
                'channel': other_channel.id,
                'requested_delivery_date': str(timezone.localdate() + timedelta(days=7)),
                'payment_terms_days': 30,
            },
        )
        approve_response = client.post(
            f'/api/crm/orders/{order.id}/approve/',
        )

        assert invalid_response.status_code == 201
        assert approve_response.status_code == 200
        assert approve_response.json()['status'] == SalesOrder.Status.APPROVED
        assert approve_response.json()['approved_by'] == user.id
