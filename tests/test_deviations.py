from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.models import StockLot, StockQualityStatus
from masters.models import BusinessPartner, Product, UnitOfMeasure


User = get_user_model()


def create_deviation_context(suffix='001'):
    from documents.models import ControlledDocument

    owner = User.objects.create_user(
        username=f'doc-owner-{suffix}@example.com',
        email=f'doc-owner-{suffix}@example.com',
        password='S3curePass!123',
    )
    unit = UnitOfMeasure.objects.create(code=f'UN-DV-{suffix}', name='Unidade', symbol='un')
    product = Product.objects.create(
        code=f'DEV-PROD-{suffix}',
        description=f'Produto desvio {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    lot = StockLot.objects.create(
        product=product,
        lot_number=f'DEV-LOTE-{suffix}',
        quality_status=StockQualityStatus.QUARANTINE,
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    supplier = BusinessPartner.objects.create(
        code=f'FOR-DV-{suffix}',
        legal_name=f'Fornecedor Desvio {suffix}',
        partner_type=BusinessPartner.PartnerType.SUPPLIER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    customer = BusinessPartner.objects.create(
        code=f'CLI-DV-{suffix}',
        legal_name=f'Cliente Desvio {suffix}',
        partner_type=BusinessPartner.PartnerType.CUSTOMER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    document = ControlledDocument.objects.create(
        document_type=ControlledDocument.DocumentType.SOP,
        code=f'POP-DV-{suffix}',
        title=f'Procedimento de investigação {suffix}',
        area='Garantia da Qualidade',
        version='1.0',
        effective_from=timezone.localdate(),
        valid_until=timezone.localdate() + timedelta(days=365),
        owner=owner,
        content='Procedimento para investigação de desvios.',
        change_summary='Emissão inicial.',
    )
    document.submit_for_review(user=owner)
    document.review(user=owner, comments='Revisado.')
    document.approve(user=owner, comments='Aprovado.')
    document.publish(user=owner)
    return unit, product, lot, supplier, customer, document


def create_quality_oos_result(unit, product, lot, suffix='001'):
    from quality.models import (
        AnalyticalSpecification,
        QualityAnalysis,
        QualityResult,
        QualitySample,
    )

    specification = AnalyticalSpecification.objects.create(
        product=product,
        stock_lot=lot,
        version=f'v-dv-{suffix}',
        method_code=f'MET-DV-{suffix}',
        method_name='Teor por HPLC',
        parameter_name='Teor',
        unit=unit,
        lower_limit=Decimal('90.0000'),
        upper_limit=Decimal('110.0000'),
        acceptance_criteria='Teor entre 90 e 110.',
        effective_from=timezone.localdate(),
    )
    sample = QualitySample.objects.create(
        sample_type=QualitySample.SampleType.PRODUCTION,
        product=product,
        stock_lot=lot,
        specification=specification,
        quantity=Decimal('1.0000'),
        unit=unit,
        status=QualitySample.Status.APPROVED,
    )
    analysis = QualityAnalysis.objects.create(
        sample=sample,
        specification=specification,
        status=QualityAnalysis.Status.APPROVED,
        method_reference=specification.method_code,
    )
    return QualityResult.objects.create(
        analysis=analysis,
        specification=specification,
        parameter_name='Teor',
        result_type=QualityResult.ResultType.QUANTITATIVE,
        numeric_result=Decimal('120.0000'),
        unit=unit,
        result_status=QualityResult.ResultStatus.OUT_OF_SPECIFICATION,
    )


class DeviationModelTests(TestCase):
    def test_deviation_requires_investigation_impact_and_required_approval_before_closure(self):
        from deviations.models import (
            DeviationApproval,
            DeviationEvidence,
            DeviationImpactAssessment,
            DeviationInvestigation,
            QualityEvent,
        )

        responsible = User.objects.create_user(
            username='responsavel@example.com',
            email='responsavel@example.com',
            password='S3curePass!123',
        )
        qa_approver = User.objects.create_user(
            username='qa.aprovador@example.com',
            email='qa.aprovador@example.com',
            password='S3curePass!123',
        )
        _unit, product, lot, supplier, customer, document = create_deviation_context()
        event = QualityEvent.objects.create(
            event_type=QualityEvent.EventType.DEVIATION,
            origin=QualityEvent.Origin.MANUAL,
            area='Compressão',
            product=product,
            stock_lot=lot,
            controlled_document=document,
            supplier=supplier,
            customer=customer,
            severity=QualityEvent.Severity.HIGH,
            criticality=QualityEvent.Criticality.CRITICAL,
            description='Reconciliação de embalagem fora do limite aprovado.',
            detected_at=timezone.now(),
            responsible=responsible,
            opened_by=responsible,
        )
        DeviationEvidence.objects.create(
            event=event,
            title='Foto da reconciliação',
            file_reference='evidencias/desvio-001.pdf',
            content_hash='sha256:def456',
            uploaded_by=responsible,
        )

        with pytest.raises(ValidationError) as no_investigation:
            event.close(summary='Encerramento sem investigação.', user=qa_approver)

        investigation = DeviationInvestigation.objects.create(
            event=event,
            investigator=responsible,
            immediate_actions='Segregação do lote e conferência da linha.',
            containment_actions='Bloqueio preventivo do lote afetado.',
        )
        investigation.conclude(
            root_cause='Falha na dupla checagem da reconciliação.',
            impact_conclusion='Impacto restrito ao lote avaliado.',
            conclusion='Investigação concluída com causa raiz definida.',
            user=responsible,
        )

        with pytest.raises(ValidationError) as no_impact:
            event.close(summary='Encerramento sem impacto.', user=qa_approver)

        impact = DeviationImpactAssessment.objects.create(
            event=event,
            impacts_quality=True,
            impacts_safety=False,
            impacts_efficacy=False,
            impacts_regulatory=True,
            impacts_patient=False,
            impacts_inventory=True,
            impacts_cost=True,
            impacts_deadline=True,
            summary='Impacto em qualidade, estoque, custo e prazo identificado.',
            assessed_by=responsible,
        )
        impact.complete(user=responsible)

        approval = DeviationApproval.objects.create(
            event=event,
            approver=qa_approver,
            role=DeviationApproval.Role.QA,
            required=True,
        )
        with pytest.raises(ValidationError) as no_approval:
            event.close(summary='Encerramento sem aprovação.', user=qa_approver)

        approval.approve(user=qa_approver, comments='Investigação e impacto aprovados.')
        event.close(
            summary='Desvio encerrado com ações imediatas e contenção concluídas.', user=qa_approver
        )

        event.refresh_from_db()
        assert 'investigation' in no_investigation.value.message_dict
        assert 'impact_assessment' in no_impact.value.message_dict
        assert 'approvals' in no_approval.value.message_dict
        assert event.status == QualityEvent.Status.CLOSED
        assert event.closed_by == qa_approver
        assert event.closed_at is not None

    def test_deviation_links_to_complaint_oos_lot_document_and_future_references(self):
        from crm.models import CustomerComplaint
        from deviations.models import DeviationLink, QualityEvent

        responsible = User.objects.create_user(
            username='link.responsavel@example.com',
            email='link.responsavel@example.com',
            password='S3curePass!123',
        )
        unit, product, lot, supplier, customer, document = create_deviation_context()
        oos_result = create_quality_oos_result(unit, product, lot)
        complaint = CustomerComplaint.objects.create(
            customer=customer,
            product=product,
            stock_lot=lot,
            quality_reference='OOS-2026-001',
            description='Cliente relatou divergência visual no lote.',
            severity=CustomerComplaint.Severity.HIGH,
        )
        event = QualityEvent.objects.create(
            event_type=QualityEvent.EventType.NONCONFORMITY,
            origin=QualityEvent.Origin.CUSTOMER_COMPLAINT,
            area='Atendimento técnico',
            product=product,
            stock_lot=lot,
            controlled_document=document,
            supplier=supplier,
            customer=customer,
            severity=QualityEvent.Severity.MEDIUM,
            criticality=QualityEvent.Criticality.MAJOR,
            description='Não conformidade aberta a partir de reclamação de cliente.',
            detected_at=timezone.now(),
            responsible=responsible,
            opened_by=responsible,
        )
        links = [
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.COMPLAINT,
                customer_complaint=complaint,
            ),
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.OOS_OOT,
                quality_result=oos_result,
            ),
            DeviationLink.objects.create(
                event=event, link_type=DeviationLink.LinkType.LOT, stock_lot=lot
            ),
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.DOCUMENT,
                controlled_document=document,
            ),
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.CAPA,
                reference_code='CAPA-2026-001',
            ),
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.CHANGE,
                reference_code='MUD-2026-001',
            ),
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.AUDIT,
                reference_code='AUD-2026-001',
            ),
            DeviationLink.objects.create(
                event=event,
                link_type=DeviationLink.LinkType.RISK,
                reference_code='RISK-2026-001',
            ),
        ]

        assert DeviationLink.objects.filter(event=event).count() == 8
        assert {link.link_type for link in links} >= {
            DeviationLink.LinkType.COMPLAINT,
            DeviationLink.LinkType.OOS_OOT,
            DeviationLink.LinkType.LOT,
            DeviationLink.LinkType.DOCUMENT,
            DeviationLink.LinkType.CAPA,
            DeviationLink.LinkType.CHANGE,
            DeviationLink.LinkType.AUDIT,
            DeviationLink.LinkType.RISK,
        }


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestDeviationApi:
    def test_deviation_api_uses_global_scope_and_closes_after_required_records(self):
        from deviations.models import DeviationApproval, QualityEvent

        responsible = User.objects.create_user(
            username='api.responsavel@example.com',
            email='api.responsavel@example.com',
            password='S3curePass!123',
        )
        approver = User.objects.create_user(
            username='api.aprovador@example.com',
            email='api.aprovador@example.com',
            password='S3curePass!123',
        )
        _unit, product, lot, supplier, customer, document = create_deviation_context()
        (
            _other_unit,
            other_product,
            _other_lot,
            _other_supplier,
            _other_customer,
            _other_document,
        ) = create_deviation_context(suffix='999')
        QualityEvent.objects.create(
            event_type=QualityEvent.EventType.DEVIATION,
            origin=QualityEvent.Origin.MANUAL,
            area='Global secundário',
            product=other_product,
            severity=QualityEvent.Severity.LOW,
            criticality=QualityEvent.Criticality.MINOR,
            description='Evento de global secundário.',
            detected_at=timezone.now(),
        )
        client = APIClient()
        client.force_authenticate(responsible)

        invalid_response = client.post(
            '/api/deviations/events/',
            {
                'event_type': QualityEvent.EventType.DEVIATION,
                'origin': QualityEvent.Origin.MANUAL,
                'area': 'Compressão',
                'product': other_product.id,
                'severity': QualityEvent.Severity.HIGH,
                'criticality': QualityEvent.Criticality.CRITICAL,
                'description': 'Produto de global secundário.',
                'detected_at': timezone.now().isoformat(),
                'responsible': responsible.id,
            },
        )
        create_response = client.post(
            '/api/deviations/events/',
            {
                'event_type': QualityEvent.EventType.DEVIATION,
                'origin': QualityEvent.Origin.MANUAL,
                'area': 'Compressão',
                'product': product.id,
                'stock_lot': lot.id,
                'controlled_document': document.id,
                'supplier': supplier.id,
                'customer': customer.id,
                'severity': QualityEvent.Severity.HIGH,
                'criticality': QualityEvent.Criticality.CRITICAL,
                'description': 'Falha na reconciliação de embalagem.',
                'detected_at': timezone.now().isoformat(),
                'responsible': responsible.id,
            },
        )
        event_id = create_response.json()['id']
        start_response = client.post(
            f'/api/deviations/events/{event_id}/start_investigation/',
        )
        investigation_response = client.post(
            '/api/deviations/investigations/',
            {
                'event': event_id,
                'investigator': responsible.id,
                'immediate_actions': 'Segregar lote.',
                'containment_actions': 'Bloquear uso até conclusão.',
            },
        )
        investigation_id = investigation_response.json()['id']
        conclude_response = client.post(
            f'/api/deviations/investigations/{investigation_id}/conclude/',
            {
                'root_cause': 'Falha de checagem.',
                'impact_conclusion': 'Impacto limitado.',
                'conclusion': 'Investigação concluída.',
            },
        )
        impact_response = client.post(
            '/api/deviations/impact-assessments/',
            {
                'event': event_id,
                'impacts_quality': True,
                'impacts_regulatory': True,
                'impacts_inventory': True,
                'summary': 'Impacto avaliado.',
                'assessed_by': responsible.id,
            },
        )
        impact_id = impact_response.json()['id']
        complete_impact_response = client.post(
            f'/api/deviations/impact-assessments/{impact_id}/complete/',
        )
        approval_response = client.post(
            '/api/deviations/approvals/',
            {
                'event': event_id,
                'approver': approver.id,
                'role': DeviationApproval.Role.QA,
                'required': True,
            },
        )
        client.force_authenticate(approver)
        approval_id = approval_response.json()['id']
        approve_response = client.post(
            f'/api/deviations/approvals/{approval_id}/approve/',
            {'comments': 'Aprovado.'},
        )
        close_response = client.post(
            f'/api/deviations/events/{event_id}/close/',
            {'summary': 'Evento encerrado após investigação, impacto e aprovação.'},
        )
        list_response = client.get('/api/deviations/events/')

        assert invalid_response.status_code == 201
        assert create_response.status_code == 201
        assert start_response.status_code == 200
        assert investigation_response.status_code == 201
        assert conclude_response.status_code == 200
        assert impact_response.status_code == 201
        assert complete_impact_response.status_code == 200
        assert approval_response.status_code == 201
        assert approve_response.status_code == 200
        assert close_response.status_code == 200
        assert close_response.json()['status'] == QualityEvent.Status.CLOSED
        assert {item['description'] for item in list_response.json()['results']} == {
            'Evento de global secundário.',
            'Falha na reconciliação de embalagem.',
            'Produto de global secundário.',
        }
