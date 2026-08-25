from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from documents.models import ControlledDocument
from inventory.models import StockLot, StockQualityStatus
from masters.models import BusinessPartner, Product, UnitOfMeasure


User = get_user_model()


def create_pharmacovigilance_context(owner, suffix='001'):
    unit = UnitOfMeasure.objects.create(code=f'UN-PV-{suffix}', name='Unidade', symbol='un')
    product = Product.objects.create(
        code=f'PV-PROD-{suffix}',
        description=f'Produto Farmacovigilância {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    lot = StockLot.objects.create(
        product=product,
        lot_number=f'PV-LOTE-{suffix}',
        quality_status=StockQualityStatus.APPROVED,
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    customer = BusinessPartner.objects.create(
        code=f'CLI-PV-{suffix}',
        legal_name=f'Cliente Farmacovigilância {suffix}',
        partner_type=BusinessPartner.PartnerType.CUSTOMER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    document = ControlledDocument.objects.create(
        document_type=ControlledDocument.DocumentType.REPORT,
        code=f'REL-PV-{suffix}',
        title=f'Relatório de Segurança {suffix}',
        area='Farmacovigilância',
        version='1.0',
        effective_from=timezone.localdate(),
        owner=owner,
        content='Documento de suporte ao caso de farmacovigilância.',
        change_summary='Emissão inicial.',
    )
    return product, lot, customer, document


class PharmacovigilanceModelTests(TestCase):
    def test_case_blocks_closure_until_triage_classification_causality_actions_and_report(self):
        from pharmacovigilance.models import (
            PharmacovigilanceAction,
            PharmacovigilanceCase,
            PharmacovigilanceCausalityAssessment,
            PharmacovigilanceClassification,
            PharmacovigilanceInvestigation,
            PharmacovigilanceSafetyReport,
        )

        owner = User.objects.create_user(
            username='pv.owner@example.com', email='pv.owner@example.com', password='S3curePass!123'
        )
        reviewer = User.objects.create_user(
            username='pv.reviewer@example.com',
            email='pv.reviewer@example.com',
            password='S3curePass!123',
        )
        product, lot, customer, _document = create_pharmacovigilance_context(owner)
        case = PharmacovigilanceCase.objects.create(
            case_type=PharmacovigilanceCase.CaseType.ADVERSE_EVENT,
            source=PharmacovigilanceCase.Source.HEALTHCARE_PROFESSIONAL,
            product=product,
            stock_lot=lot,
            customer=customer,
            patient_identifier_hash='sha256:patient-001',
            patient_age=42,
            patient_gender='female',
            country='BR',
            seriousness=PharmacovigilanceCase.Seriousness.SERIOUS,
            severity=PharmacovigilanceCase.Severity.HIGH,
            outcome=PharmacovigilanceCase.Outcome.RECOVERING,
            description='Paciente reportou reação adversa grave após administração.',
            event_started_at=timezone.now() - timedelta(days=2),
            event_reported_at=timezone.now() - timedelta(days=1),
            responsible=owner,
            reported_by=owner,
        )

        with pytest.raises(ValidationError) as investigation_without_triage:
            case.start_investigation(user=owner)

        case.start_triage(user=owner)

        with pytest.raises(ValidationError) as no_classification:
            case.close(summary='Tentativa sem classificação.', user=reviewer)

        PharmacovigilanceClassification.objects.create(
            case=case,
            category=PharmacovigilanceClassification.Category.ADVERSE_REACTION,
            seriousness=PharmacovigilanceClassification.Seriousness.SERIOUS,
            expectedness=PharmacovigilanceClassification.Expectedness.UNEXPECTED,
            listedness_reference='Bula vigente v1.0',
            classified_by=owner,
            notes='Evento não descrito na bula vigente.',
        )
        case.start_investigation(user=owner)

        with pytest.raises(ValidationError) as no_causality:
            case.close(summary='Tentativa sem causalidade.', user=reviewer)

        investigation = PharmacovigilanceInvestigation.objects.create(
            case=case,
            summary='Investigação de prontuário, lote e histórico clínico.',
            root_cause='Causa em avaliação.',
            conclusion='Dados compatíveis com possível reação adversa.',
            responsible=owner,
        )
        investigation.complete(user=reviewer)
        PharmacovigilanceCausalityAssessment.objects.create(
            case=case,
            method=PharmacovigilanceCausalityAssessment.Method.WHO_UMC,
            result=PharmacovigilanceCausalityAssessment.Result.POSSIBLE,
            rationale='Relação temporal plausível e fatores de confusão presentes.',
            assessed_by=reviewer,
        )
        action = PharmacovigilanceAction.objects.create(
            case=case,
            action_type=PharmacovigilanceAction.ActionType.REGULATORY_NOTIFICATION,
            title='Notificar evento adverso sério',
            description='Preparar submissão de segurança à autoridade sanitária.',
            responsible=owner,
            due_date=timezone.localdate() + timedelta(days=7),
            mandatory=True,
            evidence_required=True,
        )

        with pytest.raises(ValidationError) as no_completed_actions:
            case.close(summary='Tentativa sem ações concluídas.', user=reviewer)

        action.complete(
            completion_notes='Notificação preparada e revisada.',
            evidence_reference='farmacovigilancia/notificacao-eas.pdf',
            content_hash='sha256:notificacao-eas',
            user=owner,
        )

        with pytest.raises(ValidationError) as no_report:
            case.close(summary='Tentativa sem relatório gerado.', user=reviewer)

        report = PharmacovigilanceSafetyReport.objects.create(
            case=case,
            report_type=PharmacovigilanceSafetyReport.ReportType.SAFETY_CASE,
            title='Relatório individual de segurança',
        )
        report.generate(
            user=reviewer, content_reference='farmacovigilancia/relatorio-seguranca.pdf'
        )
        case.close(
            summary='Caso encerrado com investigação, causalidade, ação e relatório.', user=reviewer
        )

        case.refresh_from_db()
        investigation.refresh_from_db()
        report.refresh_from_db()
        assert 'status' in investigation_without_triage.value.message_dict
        assert 'classifications' in no_classification.value.message_dict
        assert 'causality_assessments' in no_causality.value.message_dict
        assert 'actions' in no_completed_actions.value.message_dict
        assert 'reports' in no_report.value.message_dict
        assert case.status == PharmacovigilanceCase.Status.CLOSED
        assert case.closed_by == reviewer
        assert investigation.status == PharmacovigilanceInvestigation.Status.COMPLETED
        assert action.status == PharmacovigilanceAction.Status.COMPLETED
        assert report.status == PharmacovigilanceSafetyReport.Status.GENERATED
        assert report.case_count == 1
        assert report.serious_cases == 1
        assert report.recurrence_count == 1

    def test_pharmacovigilance_supports_case_types_links_and_recurrence_indicators(self):
        from pharmacovigilance.models import (
            PharmacovigilanceCase,
            PharmacovigilanceLink,
            PharmacovigilanceSafetyReport,
        )

        owner = User.objects.create_user(
            username='pv.indicator.owner@example.com',
            email='pv.indicator.owner@example.com',
            password='S3curePass!123',
        )
        product, _lot, _customer, _document = create_pharmacovigilance_context(owner)
        first_case = PharmacovigilanceCase.objects.create(
            case_type=PharmacovigilanceCase.CaseType.TECHNICAL_COMPLAINT,
            source=PharmacovigilanceCase.Source.CUSTOMER,
            product=product,
            country='BR',
            seriousness=PharmacovigilanceCase.Seriousness.NON_SERIOUS,
            severity=PharmacovigilanceCase.Severity.MEDIUM,
            outcome=PharmacovigilanceCase.Outcome.NOT_APPLICABLE,
            description='Queixa técnica com possível impacto de segurança.',
            event_reported_at=timezone.now() - timedelta(days=3),
            responsible=owner,
            reported_by=owner,
        )
        PharmacovigilanceCase.objects.create(
            case_type=PharmacovigilanceCase.CaseType.TECHNICAL_COMPLAINT,
            source=PharmacovigilanceCase.Source.CUSTOMER,
            product=product,
            country='BR',
            seriousness=PharmacovigilanceCase.Seriousness.NON_SERIOUS,
            severity=PharmacovigilanceCase.Severity.LOW,
            outcome=PharmacovigilanceCase.Outcome.NOT_APPLICABLE,
            description='Segunda queixa técnica recorrente para o mesmo produto.',
            event_reported_at=timezone.now() - timedelta(days=1),
            responsible=owner,
            reported_by=owner,
        )
        report = PharmacovigilanceSafetyReport.objects.create(
            case=first_case,
            report_type=PharmacovigilanceSafetyReport.ReportType.TREND,
            title='Tendência de queixas técnicas',
        )

        report.generate(user=owner, content_reference='farmacovigilancia/tendencia-queixas.pdf')

        assert {
            PharmacovigilanceCase.CaseType.ADVERSE_EVENT,
            PharmacovigilanceCase.CaseType.TECHNICAL_COMPLAINT,
            PharmacovigilanceCase.CaseType.SUSPECTED_DEVIATION,
            PharmacovigilanceCase.CaseType.PATIENT_COMPLAINT,
            PharmacovigilanceCase.CaseType.SAFETY_NOTIFICATION,
        }.issubset(set(PharmacovigilanceCase.CaseType.values))
        assert {
            PharmacovigilanceLink.LinkType.COMPLAINT,
            PharmacovigilanceLink.LinkType.DEVIATION,
            PharmacovigilanceLink.LinkType.CAPA,
            PharmacovigilanceLink.LinkType.RECALL,
            PharmacovigilanceLink.LinkType.LOT,
            PharmacovigilanceLink.LinkType.CUSTOMER,
            PharmacovigilanceLink.LinkType.PRODUCT,
            PharmacovigilanceLink.LinkType.REGULATORY_DOSSIER,
            PharmacovigilanceLink.LinkType.DOCUMENT,
        }.issubset(set(PharmacovigilanceLink.LinkType.values))
        assert report.status == PharmacovigilanceSafetyReport.Status.GENERATED
        assert report.case_count == 2
        assert report.serious_cases == 0
        assert report.recurrence_count == 2


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestPharmacovigilanceApi:
    def test_pharmacovigilance_api_uses_global_scope_and_executes_required_workflow(self):
        from pharmacovigilance.models import (
            PharmacovigilanceAction,
            PharmacovigilanceCase,
            PharmacovigilanceCausalityAssessment,
            PharmacovigilanceClassification,
            PharmacovigilanceLink,
            PharmacovigilanceSafetyReport,
        )

        owner = User.objects.create_user(
            username='api.pv.owner@example.com',
            email='api.pv.owner@example.com',
            password='S3curePass!123',
        )
        User.objects.create_user(
            username='api.pv.reviewer@example.com',
            email='api.pv.reviewer@example.com',
            password='S3curePass!123',
        )
        other_owner = User.objects.create_user(
            username='api.pv.other@example.com',
            email='api.pv.other@example.com',
            password='S3curePass!123',
        )
        product, lot, customer, document = create_pharmacovigilance_context(owner, suffix='001')
        other_product, _other_lot, _other_customer, _other_document = (
            create_pharmacovigilance_context(other_owner, suffix='999')
        )
        PharmacovigilanceCase.objects.create(
            case_type=PharmacovigilanceCase.CaseType.SAFETY_NOTIFICATION,
            source=PharmacovigilanceCase.Source.AUTHORITY,
            product=other_product,
            country='BR',
            seriousness=PharmacovigilanceCase.Seriousness.NON_SERIOUS,
            severity=PharmacovigilanceCase.Severity.MEDIUM,
            outcome=PharmacovigilanceCase.Outcome.UNKNOWN,
            description='Caso secundario para validar listagem global.',
            event_reported_at=timezone.now(),
            responsible=other_owner,
            reported_by=other_owner,
        )

        client = APIClient()
        client.force_authenticate(owner)

        case_response = client.post(
            '/api/pharmacovigilance/cases/',
            {
                'case_type': PharmacovigilanceCase.CaseType.ADVERSE_EVENT,
                'source': PharmacovigilanceCase.Source.PATIENT,
                'product': product.id,
                'stock_lot': lot.id,
                'customer': customer.id,
                'patient_identifier_hash': 'sha256:api-patient-001',
                'patient_age': 58,
                'patient_gender': 'male',
                'country': 'BR',
                'seriousness': PharmacovigilanceCase.Seriousness.SERIOUS,
                'severity': PharmacovigilanceCase.Severity.CRITICAL,
                'outcome': PharmacovigilanceCase.Outcome.RECOVERING,
                'description': 'Evento adverso sério recebido por atendimento ao paciente.',
                'event_started_at': (timezone.now() - timedelta(days=2)).isoformat(),
                'event_reported_at': (timezone.now() - timedelta(days=1)).isoformat(),
                'responsible': owner.id,
            },
        )
        case_id = case_response.json()['id']
        invalid_link_response = client.post(
            '/api/pharmacovigilance/links/',
            {
                'case': case_id,
                'link_type': PharmacovigilanceLink.LinkType.PRODUCT,
                'product': other_product.id,
                'description': 'Produto secundario vinculado ao caso global.',
            },
        )
        link_payloads = [
            {'link_type': 'product', 'product': product.id, 'description': 'Produto do caso.'},
            {'link_type': 'lot', 'stock_lot': lot.id, 'description': 'Lote reportado.'},
            {
                'link_type': 'customer',
                'customer': customer.id,
                'description': 'Cliente notificador.',
            },
            {
                'link_type': 'document',
                'document': document.id,
                'description': 'Documento de suporte.',
            },
            {
                'link_type': 'recall',
                'reference_code': 'RECALL-2026-0001',
                'description': 'Recolhimento relacionado.',
            },
        ]
        link_responses = [
            client.post(
                '/api/pharmacovigilance/links/',
                {'case': case_id, **payload},
            )
            for payload in link_payloads
        ]
        triage_response = client.post(f'/api/pharmacovigilance/cases/{case_id}/start_triage/')
        classification_response = client.post(
            '/api/pharmacovigilance/classifications/',
            {
                'case': case_id,
                'category': PharmacovigilanceClassification.Category.ADVERSE_REACTION,
                'seriousness': PharmacovigilanceClassification.Seriousness.SERIOUS,
                'expectedness': PharmacovigilanceClassification.Expectedness.UNEXPECTED,
                'listedness_reference': 'Bula v1.0',
                'notes': 'Evento não esperado.',
            },
        )
        investigation_start_response = client.post(
            f'/api/pharmacovigilance/cases/{case_id}/start_investigation/',
        )
        investigation_response = client.post(
            '/api/pharmacovigilance/investigations/',
            {
                'case': case_id,
                'summary': 'Investigação API com avaliação de lote e histórico clínico.',
                'root_cause': 'Causa em avaliação por dados clínicos.',
                'conclusion': 'Causalidade possível e sem evidência de falha de lote.',
                'responsible': owner.id,
            },
        )
        investigation_id = investigation_response.json()['id']
        investigation_complete_response = client.post(
            f'/api/pharmacovigilance/investigations/{investigation_id}/complete/',
        )
        causality_response = client.post(
            '/api/pharmacovigilance/causality-assessments/',
            {
                'case': case_id,
                'method': PharmacovigilanceCausalityAssessment.Method.WHO_UMC,
                'result': PharmacovigilanceCausalityAssessment.Result.POSSIBLE,
                'rationale': 'Relação temporal plausível.',
            },
        )
        action_response = client.post(
            '/api/pharmacovigilance/actions/',
            {
                'case': case_id,
                'action_type': PharmacovigilanceAction.ActionType.REGULATORY_NOTIFICATION,
                'title': 'Notificação sanitária',
                'description': 'Notificar autoridade sanitária.',
                'responsible': owner.id,
                'due_date': str(timezone.localdate() + timedelta(days=7)),
                'mandatory': True,
                'evidence_required': True,
            },
        )
        action_id = action_response.json()['id']
        action_complete_response = client.post(
            f'/api/pharmacovigilance/actions/{action_id}/complete/',
            {
                'completion_notes': 'Notificação revisada.',
                'evidence_reference': 'farmacovigilancia/api-notificacao.pdf',
                'content_hash': 'sha256:apinotificacao',
            },
        )
        report_response = client.post(
            '/api/pharmacovigilance/reports/',
            {
                'case': case_id,
                'report_type': PharmacovigilanceSafetyReport.ReportType.SAFETY_CASE,
                'title': 'Relatório API de segurança',
            },
        )
        report_id = report_response.json()['id']
        report_generate_response = client.post(
            f'/api/pharmacovigilance/reports/{report_id}/generate/',
            {'content_reference': 'farmacovigilancia/api-relatorio-seguranca.pdf'},
        )
        close_response = client.post(
            f'/api/pharmacovigilance/cases/{case_id}/close/',
            {'summary': 'Caso API encerrado com requisitos completos.'},
        )
        list_response = client.get('/api/pharmacovigilance/cases/')

        assert case_response.status_code == 201
        assert invalid_link_response.status_code == 201
        assert all(response.status_code == 201 for response in link_responses)
        assert triage_response.status_code == 200
        assert classification_response.status_code == 201
        assert investigation_start_response.status_code == 200
        assert investigation_response.status_code == 201
        assert investigation_complete_response.status_code == 200
        assert causality_response.status_code == 201
        assert action_response.status_code == 201
        assert action_complete_response.status_code == 200
        assert report_response.status_code == 201
        assert report_generate_response.status_code == 200
        assert close_response.status_code == 200
        assert close_response.json()['status'] == PharmacovigilanceCase.Status.CLOSED
        assert list_response.status_code == 200
        assert case_response.json()['case_number'] in {
            item['case_number'] for item in list_response.json()['results']
        }
