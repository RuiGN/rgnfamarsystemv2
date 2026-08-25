from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from documents.models import ControlledDocument
from masters.models import BusinessPartner, Product, UnitOfMeasure


User = get_user_model()


def create_risk_context(owner, suffix='001'):
    unit = UnitOfMeasure.objects.create(code=f'UN-RSK-{suffix}', name='Unidade', symbol='un')
    product = Product.objects.create(
        code=f'RSK-PROD-{suffix}',
        description=f'Produto Risco {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    supplier = BusinessPartner.objects.create(
        code=f'FOR-RSK-{suffix}',
        legal_name=f'Fornecedor Risco {suffix}',
        partner_type=BusinessPartner.PartnerType.SUPPLIER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    document = ControlledDocument.objects.create(
        document_type=ControlledDocument.DocumentType.SOP,
        code=f'POP-RSK-{suffix}',
        title=f'POP Risco {suffix}',
        area='Garantia da Qualidade',
        version='1.0',
        effective_from=timezone.localdate(),
        owner=owner,
        content='Procedimento sujeito a risco.',
        change_summary='Emissão inicial.',
    )
    return product, supplier, document


class RiskModelTests(TestCase):
    def test_risk_blocks_monitoring_and_closure_until_assessment_mitigation_residual_and_review(
        self,
    ):
        from risks.models import (
            RiskAssessment,
            RiskControl,
            RiskMitigationAction,
            RiskRecord,
            RiskReview,
        )

        owner = User.objects.create_user(
            username='risk.owner@example.com',
            email='risk.owner@example.com',
            password='S3curePass!123',
        )
        reviewer = User.objects.create_user(
            username='risk.reviewer@example.com',
            email='risk.reviewer@example.com',
            password='S3curePass!123',
        )
        product, supplier, document = create_risk_context(owner)
        risk = RiskRecord.objects.create(
            risk_category=RiskRecord.RiskCategory.QUALITY,
            title='Risco de contaminação cruzada na compressão',
            description='Falha de limpeza pode impactar segurança e eficácia.',
            process_area='Compressão',
            owner=owner,
            due_date=timezone.localdate() + timedelta(days=45),
            next_review_date=timezone.localdate() + timedelta(days=90),
            identified_by=owner,
        )

        RiskControl.objects.create(
            risk=risk,
            control_type=RiskControl.ControlType.PREVENTIVE,
            title='POP de limpeza validada',
            description='Procedimento vigente com dupla checagem QA.',
            owner=owner,
            evidence_reference='controles/pop-limpeza.pdf',
            content_hash='sha256:poplimpeza',
        )

        with pytest.raises(ValidationError) as no_assessment:
            risk.start_treatment(user=owner)

        initial_assessment = RiskAssessment.objects.create(
            risk=risk,
            assessment_type=RiskAssessment.AssessmentType.INITIAL,
            method=RiskAssessment.Method.FMEA,
            probability=5,
            severity=5,
            detectability=4,
            rationale='Falha rara, mas com impacto crítico e baixa detectabilidade em linha.',
            assessed_by=owner,
        )
        risk.start_treatment(user=owner)

        with pytest.raises(ValidationError) as no_actions:
            risk.start_monitoring(user=reviewer)

        action = RiskMitigationAction.objects.create(
            risk=risk,
            action_type=RiskMitigationAction.ActionType.MITIGATION,
            title='Revalidar limpeza e treinar operadores',
            description='Executar bracketing, revisar POP e treinar equipe.',
            responsible=owner,
            due_date=timezone.localdate() + timedelta(days=15),
            mandatory=True,
            evidence_required=True,
        )

        with pytest.raises(ValidationError) as action_pending:
            risk.start_monitoring(user=reviewer)

        action.complete(
            user=owner,
            completion_notes='Revalidação concluída e treinamento executado.',
            evidence_reference='riscos/revalidacao-limpeza.pdf',
            content_hash='sha256:revalidacaolimpeza',
        )

        with pytest.raises(ValidationError) as no_residual:
            risk.start_monitoring(user=reviewer)

        residual_assessment = RiskAssessment.objects.create(
            risk=risk,
            assessment_type=RiskAssessment.AssessmentType.RESIDUAL,
            method=RiskAssessment.Method.FMEA,
            probability=2,
            severity=4,
            detectability=2,
            rationale='Controles mitigados reduzem probabilidade e melhoram detecção.',
            assessed_by=reviewer,
        )
        risk.start_monitoring(user=reviewer)

        with pytest.raises(ValidationError) as no_review:
            risk.close(summary='Tentativa sem revisão concluída.', user=reviewer)

        review = RiskReview.objects.create(
            risk=risk,
            planned_date=timezone.localdate(),
            reviewer=reviewer,
            review_scope='Revisão pós-mitigação de risco residual.',
        )
        review.complete(
            result='Risco residual aceitável para monitoramento de rotina.',
            next_review_date=timezone.localdate() + timedelta(days=180),
            user=reviewer,
        )
        risk.close(summary='Risco residual aceito e monitorado.', user=reviewer)

        risk.refresh_from_db()
        initial_assessment.refresh_from_db()
        residual_assessment.refresh_from_db()
        assert 'assessments' in no_assessment.value.message_dict
        assert 'actions' in no_actions.value.message_dict
        assert 'actions' in action_pending.value.message_dict
        assert 'residual_risk' in no_residual.value.message_dict
        assert 'reviews' in no_review.value.message_dict
        assert initial_assessment.score == 100
        assert initial_assessment.risk_level == RiskAssessment.RiskLevel.CRITICAL
        assert residual_assessment.score == 16
        assert residual_assessment.risk_level == RiskAssessment.RiskLevel.MEDIUM
        assert risk.initial_score == 100
        assert risk.residual_score == 16
        assert risk.status == RiskRecord.Status.CLOSED
        assert risk.closed_by == reviewer
        assert risk.next_review_date == timezone.localdate() + timedelta(days=180)

    def test_risk_supports_categories_methods_links_and_alert_generation(self):
        from risks.models import (
            RiskAlert,
            RiskAssessment,
            RiskLink,
            RiskMitigationAction,
            RiskRecord,
        )

        owner = User.objects.create_user(
            username='risk.alert.owner@example.com',
            email='risk.alert.owner@example.com',
            password='S3curePass!123',
        )
        risk = RiskRecord.objects.create(
            risk_category=RiskRecord.RiskCategory.SUPPLIER,
            title='Risco crítico de ruptura de fornecedor',
            description='Fornecedor único pode parar produção de produto crítico.',
            process_area='Suprimentos',
            owner=owner,
            due_date=timezone.localdate() + timedelta(days=30),
            next_review_date=timezone.localdate() + timedelta(days=60),
            identified_by=owner,
        )
        RiskAssessment.objects.create(
            risk=risk,
            assessment_type=RiskAssessment.AssessmentType.INITIAL,
            method=RiskAssessment.Method.MATRIX,
            probability=5,
            severity=5,
            detectability=1,
            rationale='Fornecedor único e impacto de parada de linha.',
            assessed_by=owner,
        )
        RiskMitigationAction.objects.create(
            risk=risk,
            action_type=RiskMitigationAction.ActionType.CONTINGENCY,
            title='Qualificar segundo fornecedor',
            description='Abrir qualificação alternativa.',
            responsible=owner,
            due_date=timezone.localdate() - timedelta(days=1),
            mandatory=True,
            evidence_required=True,
        )

        generated = RiskAlert.generate_all()

        assert {
            RiskRecord.RiskCategory.QUALITY,
            RiskRecord.RiskCategory.PRODUCTION,
            RiskRecord.RiskCategory.SUPPLIER,
            RiskRecord.RiskCategory.PROCESS,
            RiskRecord.RiskCategory.PRODUCT,
            RiskRecord.RiskCategory.REGULATORY,
            RiskRecord.RiskCategory.FINANCIAL,
            RiskRecord.RiskCategory.FISCAL,
            RiskRecord.RiskCategory.OPERATIONS,
        } == set(RiskRecord.RiskCategory.values)
        assert {RiskAssessment.Method.MATRIX, RiskAssessment.Method.FMEA} == set(
            RiskAssessment.Method.values
        )
        assert {
            RiskLink.LinkType.PROCESS,
            RiskLink.LinkType.PRODUCT,
            RiskLink.LinkType.DOCUMENT,
            RiskLink.LinkType.DEVIATION,
            RiskLink.LinkType.CAPA,
            RiskLink.LinkType.CHANGE,
            RiskLink.LinkType.AUDIT,
            RiskLink.LinkType.SUPPLIER,
            RiskLink.LinkType.EQUIPMENT,
        }.issubset(set(RiskLink.LinkType.values))
        assert generated == 2
        assert set(RiskAlert.objects.values_list('alert_type', flat=True)) == {
            RiskAlert.AlertType.CRITICAL_RISK,
            RiskAlert.AlertType.OVERDUE_ACTION,
        }


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestRiskApi:
    def test_risk_api_uses_global_scope_and_executes_required_workflow(self):
        from risks.models import RiskAssessment, RiskMitigationAction, RiskRecord

        owner = User.objects.create_user(
            username='api.risk.owner@example.com',
            email='api.risk.owner@example.com',
            password='S3curePass!123',
        )
        reviewer = User.objects.create_user(
            username='api.risk.reviewer@example.com',
            email='api.risk.reviewer@example.com',
            password='S3curePass!123',
        )
        other_owner = User.objects.create_user(
            username='api.risk.other@example.com',
            email='api.risk.other@example.com',
            password='S3curePass!123',
        )
        product, supplier, document = create_risk_context(owner, suffix='001')
        other_product, _other_supplier, _other_document = create_risk_context(
            other_owner, suffix='999'
        )
        RiskRecord.objects.create(
            risk_category=RiskRecord.RiskCategory.OPERATIONS,
            title='Risco secundario',
            description='Registro secundario para validar listagem global.',
            process_area='Operações',
            owner=other_owner,
            due_date=timezone.localdate() + timedelta(days=20),
            next_review_date=timezone.localdate() + timedelta(days=90),
            identified_by=other_owner,
        )

        client = APIClient()
        client.force_authenticate(owner)

        risk_response = client.post(
            '/api/risks/records/',
            {
                'risk_category': RiskRecord.RiskCategory.QUALITY,
                'title': 'Risco API de contaminação cruzada',
                'description': 'Risco crítico de limpeza entre produtos.',
                'process_area': 'Compressão',
                'owner': owner.id,
                'due_date': str(timezone.localdate() + timedelta(days=45)),
                'next_review_date': str(timezone.localdate() + timedelta(days=90)),
            },
        )
        risk_id = risk_response.json()['id']
        invalid_link_response = client.post(
            '/api/risks/links/',
            {
                'risk': risk_id,
                'link_type': 'product',
                'product': other_product.id,
                'impact_description': 'Produto secundario vinculado ao risco global.',
            },
        )
        product_link_response = client.post(
            '/api/risks/links/',
            {
                'risk': risk_id,
                'link_type': 'product',
                'product': product.id,
                'impact_description': 'Produto sujeito a risco de contaminação cruzada.',
            },
        )
        document_link_response = client.post(
            '/api/risks/links/',
            {
                'risk': risk_id,
                'link_type': 'document',
                'document': document.id,
                'impact_description': 'POP de limpeza associado ao risco.',
            },
        )
        supplier_link_response = client.post(
            '/api/risks/links/',
            {
                'risk': risk_id,
                'link_type': 'supplier',
                'supplier': supplier.id,
                'impact_description': 'Fornecedor envolvido no controle preventivo.',
            },
        )
        assessment_response = client.post(
            '/api/risks/assessments/',
            {
                'risk': risk_id,
                'assessment_type': RiskAssessment.AssessmentType.INITIAL,
                'method': RiskAssessment.Method.FMEA,
                'probability': 4,
                'severity': 5,
                'detectability': 4,
                'rationale': 'Alta criticidade e detecção limitada.',
                'assessed_by': owner.id,
            },
        )
        treatment_response = client.post(f'/api/risks/records/{risk_id}/start_treatment/')
        control_response = client.post(
            '/api/risks/controls/',
            {
                'risk': risk_id,
                'control_type': 'preventive',
                'title': 'Controle API de limpeza',
                'description': 'Controle preventivo documentado.',
                'owner': owner.id,
                'evidence_reference': 'riscos/controle-api.pdf',
                'content_hash': 'sha256:controleapi',
            },
        )
        action_response = client.post(
            '/api/risks/actions/',
            {
                'risk': risk_id,
                'action_type': RiskMitigationAction.ActionType.MITIGATION,
                'title': 'Executar mitigação API',
                'description': 'Treinar equipe e revisar POP.',
                'responsible': owner.id,
                'due_date': str(timezone.localdate() + timedelta(days=10)),
                'mandatory': True,
                'evidence_required': True,
            },
        )
        action_id = action_response.json()['id']
        action_complete_response = client.post(
            f'/api/risks/actions/{action_id}/complete/',
            {
                'completion_notes': 'Mitigação executada.',
                'evidence_reference': 'riscos/mitigacao-api.pdf',
                'content_hash': 'sha256:mitigacaoapi',
            },
        )
        residual_response = client.post(
            '/api/risks/assessments/',
            {
                'risk': risk_id,
                'assessment_type': RiskAssessment.AssessmentType.RESIDUAL,
                'method': RiskAssessment.Method.FMEA,
                'probability': 2,
                'severity': 4,
                'detectability': 2,
                'rationale': 'Risco residual moderado após mitigação.',
                'assessed_by': reviewer.id,
            },
        )
        monitoring_response = client.post(f'/api/risks/records/{risk_id}/start_monitoring/')
        review_response = client.post(
            '/api/risks/reviews/',
            {
                'risk': risk_id,
                'planned_date': str(timezone.localdate()),
                'reviewer': reviewer.id,
                'review_scope': 'Revisão API de risco residual.',
            },
        )
        review_id = review_response.json()['id']
        review_complete_response = client.post(
            f'/api/risks/reviews/{review_id}/complete/',
            {
                'result': 'Risco residual aceitável.',
                'next_review_date': str(timezone.localdate() + timedelta(days=180)),
            },
        )
        close_response = client.post(
            f'/api/risks/records/{risk_id}/close/',
            {'summary': 'Risco aceito após mitigação e revisão.'},
        )
        list_response = client.get('/api/risks/records/')

        assert risk_response.status_code == 201
        assert invalid_link_response.status_code == 201
        assert product_link_response.status_code == 201
        assert document_link_response.status_code == 201
        assert supplier_link_response.status_code == 201
        assert assessment_response.status_code == 201
        assert assessment_response.json()['score'] == 80
        assert assessment_response.json()['risk_level'] == RiskAssessment.RiskLevel.CRITICAL
        assert treatment_response.status_code == 200
        assert control_response.status_code == 201
        assert action_response.status_code == 201
        assert action_complete_response.status_code == 200
        assert residual_response.status_code == 201
        assert monitoring_response.status_code == 200
        assert review_response.status_code == 201
        assert review_complete_response.status_code == 200
        assert close_response.status_code == 200
        assert close_response.json()['status'] == RiskRecord.Status.CLOSED
        assert list_response.status_code == 200
        assert {item['title'] for item in list_response.json()['results']} == {
            'Risco API de contaminação cruzada',
            'Risco secundario',
        }
