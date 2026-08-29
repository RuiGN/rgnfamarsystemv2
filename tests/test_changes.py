from datetime import timedelta
from decimal import Decimal

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


def create_change_context(owner, suffix='001'):
    unit = UnitOfMeasure.objects.create(code=f'UN-MUD-{suffix}', name='Unidade', symbol='un')
    product = Product.objects.create(
        code=f'MUD-PROD-{suffix}',
        description=f'Produto Mudança {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    lot = StockLot.objects.create(
        product=product,
        lot_number=f'MUD-LOTE-{suffix}',
        quality_status=StockQualityStatus.QUARANTINE,
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    supplier = BusinessPartner.objects.create(
        code=f'FOR-MUD-{suffix}',
        legal_name=f'Fornecedor Mudança {suffix}',
        partner_type=BusinessPartner.PartnerType.SUPPLIER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    document = ControlledDocument.objects.create(
        document_type=ControlledDocument.DocumentType.SOP,
        code=f'POP-MUD-{suffix}',
        title=f'POP Mudança {suffix}',
        area='Garantia da Qualidade',
        version='1.0',
        effective_from=timezone.localdate(),
        owner=owner,
        content='Procedimento vigente.',
        change_summary='Emissão inicial.',
    )
    return unit, product, lot, supplier, document


class ChangeControlModelTests(TestCase):
    def test_change_blocks_implementation_and_closure_until_assessments_approvals_actions_and_stock_are_done(
        self,
    ):
        from changes.models import (
            ChangeAction,
            ChangeAffectedItem,
            ChangeApproval,
            ChangeAssessment,
            ChangeControl,
            ChangeStockAssessment,
        )

        owner = User.objects.create_user(
            username='change.owner@example.com',
            email='change.owner@example.com',
            password='S3curePass!123',
        )
        qa = User.objects.create_user(
            username='change.qa@example.com',
            email='change.qa@example.com',
            password='S3curePass!123',
        )
        _unit, product, lot, supplier, document = create_change_context(owner)
        change = ChangeControl.objects.create(
            change_type=ChangeControl.ChangeType.PERMANENT,
            title='Alteração de parâmetro crítico de compressão',
            scope='Atualizar faixa operacional, POP, treinamento e validação.',
            justification='Reduzir variabilidade de peso médio sem afetar registro.',
            affected_areas='QA; QC; Produção; Engenharia; Regulatório',
            system_reference='MES-Compressao',
            validation_plan='Executar OQ/PQ e avaliação estatística.',
            training_plan='Treinar operadores e revisores QA.',
            regulatory_strategy='Avaliar necessidade de comunicação regulatória.',
            impact_summary='Impacto potencial em processo, documentação, treinamento e estoque.',
            owner=owner,
            due_date=timezone.localdate() + timedelta(days=45),
            requires_stock_assessment=True,
            requested_by=owner,
        )
        ChangeAffectedItem.objects.create(
            change=change,
            item_type=ChangeAffectedItem.ItemType.PRODUCT,
            product=product,
            impact_description='Produto acabado impactado pela faixa de compressão.',
        )
        ChangeAffectedItem.objects.create(
            change=change,
            item_type=ChangeAffectedItem.ItemType.DOCUMENT,
            document=document,
            impact_description='POP deve ser revisado antes da implementação.',
        )
        ChangeAffectedItem.objects.create(
            change=change,
            item_type=ChangeAffectedItem.ItemType.SUPPLIER,
            supplier=supplier,
            impact_description='Fornecedor deve ser comunicado sobre especificação de embalagem.',
        )
        assessment = ChangeAssessment.objects.create(
            change=change,
            department=ChangeAssessment.Department.QA,
            assessor=qa,
            impact_description='Avaliação QA pendente.',
        )
        blocking_action = ChangeAction.objects.create(
            change=change,
            action_type=ChangeAction.ActionType.DOCUMENT_UPDATE,
            title='Atualizar POP de compressão',
            description='Revisar procedimento e checklist.',
            responsible=owner,
            due_date=timezone.localdate() + timedelta(days=10),
            mandatory=True,
            required_before_implementation=True,
            evidence_required=True,
        )
        validation_action = ChangeAction.objects.create(
            change=change,
            action_type=ChangeAction.ActionType.VALIDATION,
            title='Executar validação de processo',
            description='Rodar lotes de validação e revisar relatório.',
            responsible=owner,
            due_date=timezone.localdate() + timedelta(days=25),
            mandatory=True,
            required_before_implementation=False,
            evidence_required=True,
        )
        stock_assessment = ChangeStockAssessment.objects.create(
            change=change,
            product=product,
            stock_lot=lot,
            quantity_affected=Decimal('100.0000'),
            required=True,
        )
        approval = ChangeApproval.objects.create(
            change=change, approver=qa, role=ChangeApproval.Role.QA, required=True
        )

        with pytest.raises(ValidationError) as not_approved:
            change.start_implementation(user=owner)

        change.submit(user=owner)

        with pytest.raises(ValidationError) as no_assessment:
            change.approve_for_implementation(user=qa)

        assessment.complete(
            impact_level=ChangeAssessment.ImpactLevel.HIGH,
            impact_description='Impacto relevante em documentação, processo e treinamento.',
            required_actions='Atualizar POP, treinar equipe e executar validação.',
            user=qa,
        )

        with pytest.raises(ValidationError) as no_approval:
            change.approve_for_implementation(user=qa)

        approval.approve(user=qa, comments='Mudança aprovada para preparação de implementação.')
        change.approve_for_implementation(user=qa)

        with pytest.raises(ValidationError) as no_pre_actions:
            change.start_implementation(user=owner)

        blocking_action.complete(
            user=owner,
            completion_notes='POP revisado e aprovado.',
            evidence_reference='docs/pop-compressao-v2.pdf',
            content_hash='sha256:popcompressao',
        )
        change.start_implementation(user=owner)

        with pytest.raises(ValidationError) as no_actions:
            change.close(summary='Tentativa sem validação finalizada.', user=qa)

        validation_action.complete(
            user=owner,
            completion_notes='Validação executada com resultados aceitáveis.',
            evidence_reference='validacao/relatorio-pq.pdf',
            content_hash='sha256:relatoriopq',
        )

        with pytest.raises(ValidationError) as no_stock:
            change.close(summary='Tentativa sem avaliação de estoque.', user=qa)

        stock_assessment.complete(
            decision=ChangeStockAssessment.Decision.QUARANTINE,
            assessment_summary='Lotes em quarentena até conclusão da avaliação comparativa.',
            user=qa,
        )
        change.close(summary='Mudança implementada, validada e encerrada.', user=qa)

        change.refresh_from_db()
        assert 'status' in not_approved.value.message_dict
        assert 'assessments' in no_assessment.value.message_dict
        assert 'approvals' in no_approval.value.message_dict
        assert 'actions' in no_pre_actions.value.message_dict
        assert 'actions' in no_actions.value.message_dict
        assert 'stock_assessments' in no_stock.value.message_dict
        assert change.status == ChangeControl.Status.CLOSED
        assert change.closed_by == qa

    def test_change_supports_multidisciplinary_assessments_and_required_action_plan_types(self):
        from changes.models import ChangeAction, ChangeAssessment

        assert {
            ChangeAssessment.Department.QA,
            ChangeAssessment.Department.QC,
            ChangeAssessment.Department.PRODUCTION,
            ChangeAssessment.Department.ENGINEERING,
            ChangeAssessment.Department.REGULATORY,
            ChangeAssessment.Department.FISCAL,
            ChangeAssessment.Department.FINANCE,
            ChangeAssessment.Department.OTHER,
        }.issubset(set(ChangeAssessment.Department.values))
        assert {
            ChangeAction.ActionType.DOCUMENT_UPDATE,
            ChangeAction.ActionType.TRAINING,
            ChangeAction.ActionType.VALIDATION,
            ChangeAction.ActionType.REGULATORY_COMMUNICATION,
            ChangeAction.ActionType.STOCK_ASSESSMENT,
        }.issubset(set(ChangeAction.ActionType.values))


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestChangeControlApi:
    def test_change_api_uses_global_scope_and_executes_required_workflow(self):
        from changes.models import (
            ChangeAction,
            ChangeAffectedItem,
            ChangeApproval,
            ChangeAssessment,
            ChangeControl,
            ChangeStockAssessment,
        )

        owner = User.objects.create_user(
            username='api.change.owner@example.com',
            email='api.change.owner@example.com',
            password='S3curePass!123',
        )
        approver = User.objects.create_user(
            username='api.change.qa@example.com',
            email='api.change.qa@example.com',
            password='S3curePass!123',
        )
        other_owner = User.objects.create_user(
            username='api.change.other@example.com',
            email='api.change.other@example.com',
            password='S3curePass!123',
        )
        _unit, product, lot, _supplier, _document = create_change_context(owner, suffix='001')
        _other_unit, other_product, _other_lot, _other_supplier, _other_document = (
            create_change_context(other_owner, suffix='999')
        )
        ChangeControl.objects.create(
            change_type=ChangeControl.ChangeType.PERMANENT,
            title='Mudança secundaria',
            scope='Outro escopo.',
            justification='Outra justificativa.',
            affected_areas='QA',
            owner=owner,
            due_date=timezone.localdate() + timedelta(days=30),
        )
        client = APIClient()
        client.force_authenticate(owner)

        create_response = client.post(
            '/api/changes/controls/',
            {
                'change_type': ChangeControl.ChangeType.PERMANENT,
                'title': 'Mudança API',
                'scope': 'Alterar parâmetro e documentação associada.',
                'justification': 'Reduzir variabilidade de processo.',
                'affected_areas': 'QA; QC; Produção',
                'system_reference': 'MES',
                'validation_plan': 'Executar PQ.',
                'training_plan': 'Treinar operadores.',
                'regulatory_strategy': 'Avaliação regulatória documentada.',
                'impact_summary': 'Impacto em processo, estoque e documentação.',
                'owner': owner.id,
                'due_date': str(timezone.localdate() + timedelta(days=30)),
                'requires_stock_assessment': True,
            },
        )
        change_id = create_response.json()['id']
        invalid_item_response = client.post(
            '/api/changes/affected-items/',
            {
                'change': change_id,
                'item_type': ChangeAffectedItem.ItemType.PRODUCT,
                'product': other_product.id,
                'impact_description': 'Produto secundario.',
            },
        )
        item_response = client.post(
            '/api/changes/affected-items/',
            {
                'change': change_id,
                'item_type': ChangeAffectedItem.ItemType.PRODUCT,
                'product': product.id,
                'impact_description': 'Produto afetado.',
            },
        )
        submit_response = client.post(f'/api/changes/controls/{change_id}/submit/')
        assessment_response = client.post(
            '/api/changes/assessments/',
            {
                'change': change_id,
                'department': ChangeAssessment.Department.QA,
                'assessor': approver.id,
                'impact_description': 'Avaliação QA pendente.',
            },
        )
        assessment_id = assessment_response.json()['id']
        complete_assessment_response = client.post(
            f'/api/changes/assessments/{assessment_id}/complete/',
            {
                'impact_level': ChangeAssessment.ImpactLevel.HIGH,
                'impact_description': 'Impacto em processo e documentação.',
                'required_actions': 'Atualizar POP antes da implementação.',
            },
        )
        approval_response = client.post(
            '/api/changes/approvals/',
            {
                'change': change_id,
                'approver': approver.id,
                'role': ChangeApproval.Role.QA,
                'required': True,
            },
        )
        approval_id = approval_response.json()['id']
        client.force_authenticate(approver)
        approve_response = client.post(
            f'/api/changes/approvals/{approval_id}/approve/',
            {'comments': 'Aprovado.'},
        )
        authorize_response = client.post(
            f'/api/changes/controls/{change_id}/approve_for_implementation/',
        )
        action_response = client.post(
            '/api/changes/actions/',
            {
                'change': change_id,
                'action_type': ChangeAction.ActionType.DOCUMENT_UPDATE,
                'title': 'Atualizar POP',
                'description': 'Atualização documental pré-implementação.',
                'responsible': owner.id,
                'due_date': str(timezone.localdate() + timedelta(days=5)),
                'mandatory': True,
                'required_before_implementation': True,
                'evidence_required': True,
            },
        )
        action_id = action_response.json()['id']
        blocked_start_response = client.post(
            f'/api/changes/controls/{change_id}/start_implementation/',
        )
        client.force_authenticate(owner)
        complete_action_response = client.post(
            f'/api/changes/actions/{action_id}/complete/',
            {
                'completion_notes': 'POP atualizado.',
                'evidence_reference': 'docs/pop-api.pdf',
                'content_hash': 'sha256:popapi',
            },
        )
        start_response = client.post(
            f'/api/changes/controls/{change_id}/start_implementation/',
        )
        stock_response = client.post(
            '/api/changes/stock-assessments/',
            {
                'change': change_id,
                'product': product.id,
                'stock_lot': lot.id,
                'quantity_affected': '10.0000',
                'required': True,
            },
        )
        stock_id = stock_response.json()['id']
        complete_stock_response = client.post(
            f'/api/changes/stock-assessments/{stock_id}/complete/',
            {
                'decision': ChangeStockAssessment.Decision.QUARANTINE,
                'assessment_summary': 'Lote segregado até conclusão do estudo.',
            },
        )
        client.force_authenticate(approver)
        close_response = client.post(
            f'/api/changes/controls/{change_id}/close/',
            {'summary': 'Mudança implementada e encerrada.'},
        )
        list_response = client.get('/api/changes/controls/')

        assert create_response.status_code == 201
        assert invalid_item_response.status_code == 201
        assert 'product' in invalid_item_response.json()
        assert item_response.status_code == 201
        assert submit_response.status_code == 200
        assert assessment_response.status_code == 201
        assert complete_assessment_response.status_code == 200
        assert approval_response.status_code == 201
        assert approve_response.status_code == 200
        assert authorize_response.status_code == 200
        assert action_response.status_code == 201
        assert blocked_start_response.status_code == 400
        assert 'actions' in blocked_start_response.json()
        assert complete_action_response.status_code == 200
        assert start_response.status_code == 200
        assert stock_response.status_code == 201
        assert complete_stock_response.status_code == 200
        assert close_response.status_code == 200
        assert close_response.json()['status'] == ChangeControl.Status.CLOSED
        assert {item['title'] for item in list_response.json()['results']} == {
            'Mudança API',
            'Mudança secundaria',
        }
