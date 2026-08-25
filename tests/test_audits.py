from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from documents.models import ControlledDocument
from masters.models import BusinessPartner


User = get_user_model()


def create_audit_context(owner, suffix='001'):
    supplier = BusinessPartner.objects.create(
        code=f'FOR-AUD-{suffix}',
        legal_name=f'Fornecedor Auditoria {suffix}',
        partner_type=BusinessPartner.PartnerType.SUPPLIER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    document = ControlledDocument.objects.create(
        document_type=ControlledDocument.DocumentType.SOP,
        code=f'POP-AUD-{suffix}',
        title=f'POP Auditoria {suffix}',
        area='Garantia da Qualidade',
        version='1.0',
        effective_from=timezone.localdate(),
        owner=owner,
        content='Procedimento auditável.',
        change_summary='Emissão inicial.',
    )
    return supplier, document


class AuditModelTests(TestCase):
    def test_audit_blocks_closure_without_checklist_report_evidence_and_follow_up(self):
        from audits.models import (
            AuditChecklistItem,
            AuditEvidence,
            AuditFinding,
            AuditFollowUpAction,
            AuditPlan,
            AuditProgram,
            AuditReport,
        )

        auditor = User.objects.create_user(
            username='audit.lead@example.com',
            email='audit.lead@example.com',
            password='S3curePass!123',
        )
        responsible = User.objects.create_user(
            username='audit.resp@example.com',
            email='audit.resp@example.com',
            password='S3curePass!123',
        )
        supplier, _document = create_audit_context(auditor)
        program = AuditProgram.objects.create(
            audit_type=AuditProgram.AuditType.SUPPLIER,
            title='Programa anual de auditorias de fornecedores',
            year=timezone.localdate().year,
            scope='Fornecedores críticos de materiais produtivos.',
            criteria='BPF, contrato de qualidade e qualificação vigente.',
            owner=auditor,
            starts_on=timezone.localdate(),
            ends_on=timezone.localdate() + timedelta(days=365),
        )
        plan = AuditPlan.objects.create(
            program=program,
            audit_type=AuditPlan.AuditType.SUPPLIER,
            supplier=supplier,
            title='Auditoria no fornecedor de embalagem primária',
            scope='Sistema da qualidade e controle de mudanças do fornecedor.',
            criteria='RDC aplicável, BPF e acordo técnico.',
            agenda='Abertura, tour, revisão documental, entrevistas e encerramento.',
            lead_auditor=auditor,
            auditee_name='Fornecedor Auditoria',
            area='Garantia da Qualidade',
            scheduled_start=timezone.now() + timedelta(days=1),
            scheduled_end=timezone.now() + timedelta(days=2),
        )
        item = AuditChecklistItem.objects.create(
            audit=plan,
            section='Sistema da Qualidade',
            question='O fornecedor controla mudanças críticas?',
            requirement_reference='BPF 1.4',
            required=True,
        )
        optional_item = AuditChecklistItem.objects.create(
            audit=plan,
            section='Documentação',
            question='Registros estão completos?',
            requirement_reference='ALCOA+',
            required=False,
        )
        finding = AuditFinding.objects.create(
            audit=plan,
            checklist_item=item,
            classification=AuditFinding.Classification.NONCONFORMITY,
            criticality=AuditFinding.Criticality.MAJOR,
            title='Controle de mudanças incompleto',
            description='Mudanças de processo não possuem avaliação QA documentada.',
            responsible=responsible,
            due_date=timezone.localdate() + timedelta(days=30),
        )

        with pytest.raises(ValidationError) as not_planned:
            plan.start(user=auditor)

        plan.submit(user=auditor)
        plan.start(user=auditor)

        with pytest.raises(ValidationError) as no_checklist:
            plan.complete_execution(user=auditor)

        item.answer(
            status=AuditChecklistItem.Status.NON_CONFORM,
            answer='Evidência de controle incompleto.',
            user=auditor,
        )
        optional_item.answer(
            status=AuditChecklistItem.Status.CONFORM,
            answer='Registros completos na amostra avaliada.',
            user=auditor,
        )
        plan.complete_execution(user=auditor)

        with pytest.raises(ValidationError) as no_report:
            plan.close(summary='Tentativa sem relatório.', user=auditor)

        report = AuditReport.objects.create(
            audit=plan,
            executive_summary='Auditoria com não conformidade maior.',
            conclusion='Fornecedor permanece qualificado com plano de ação obrigatório.',
            issued_by=auditor,
        )

        with pytest.raises(ValidationError) as no_evidence:
            plan.close(summary='Tentativa sem evidência.', user=auditor)

        AuditEvidence.objects.create(
            audit=plan,
            finding=finding,
            title='Evidência do controle de mudanças',
            file_reference='auditorias/evidencia-controle-mudancas.pdf',
            content_hash='sha256:evidenciacontrolemudancas',
            uploaded_by=auditor,
        )

        with pytest.raises(ValidationError) as no_action:
            plan.close(summary='Tentativa sem ação de follow-up.', user=auditor)

        action = AuditFollowUpAction.objects.create(
            finding=finding,
            title='Implantar revisão QA de mudanças do fornecedor',
            description='Fornecedor deve atualizar procedimento e treinar equipe.',
            responsible=responsible,
            due_date=timezone.localdate() + timedelta(days=20),
            mandatory=True,
            evidence_required=True,
        )
        action.complete(
            user=responsible,
            completion_notes='Procedimento revisado e treinamento concluído.',
            evidence_reference='auditorias/plano-acao-fornecedor.pdf',
            content_hash='sha256:planoacaofornecedor',
        )
        report.issue(user=auditor)
        plan.close(summary='Auditoria encerrada com plano de ação acompanhado.', user=auditor)

        plan.refresh_from_db()
        report.refresh_from_db()
        assert 'status' in not_planned.value.message_dict
        assert 'checklist' in no_checklist.value.message_dict
        assert 'report' in no_report.value.message_dict
        assert 'evidences' in no_evidence.value.message_dict
        assert 'actions' in no_action.value.message_dict
        assert plan.status == AuditPlan.Status.CLOSED
        assert plan.closed_by == auditor
        assert report.total_findings == 1
        assert report.major_findings == 1
        assert report.compliance_rate == 50

    def test_audit_supports_types_link_targets_and_compliance_indicators(self):
        from audits.models import AuditFinding, AuditFindingLink, AuditPlan, AuditProgram

        assert {
            AuditPlan.AuditType.INTERNAL,
            AuditPlan.AuditType.EXTERNAL,
            AuditPlan.AuditType.SUPPLIER,
            AuditPlan.AuditType.CUSTOMER,
            AuditPlan.AuditType.REGULATORY,
        } == set(AuditPlan.AuditType.values)
        assert {
            AuditFindingLink.LinkType.CAPA,
            AuditFindingLink.LinkType.DEVIATION,
            AuditFindingLink.LinkType.CHANGE,
            AuditFindingLink.LinkType.RISK,
            AuditFindingLink.LinkType.SUPPLIER,
            AuditFindingLink.LinkType.DOCUMENT,
            AuditFindingLink.LinkType.TRAINING,
        }.issubset(set(AuditFindingLink.LinkType.values))
        assert AuditProgram.AuditType.values == AuditPlan.AuditType.values
        assert {
            AuditFinding.Classification.NONCONFORMITY,
            AuditFinding.Classification.OBSERVATION,
            AuditFinding.Classification.OPPORTUNITY,
            AuditFinding.Classification.COMPLIANCE,
        }.issubset(set(AuditFinding.Classification.values))


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestAuditApi:
    def test_audit_api_uses_global_scope_and_executes_required_workflow(self):
        from audits.models import (
            AuditChecklistItem,
            AuditFinding,
            AuditFindingLink,
            AuditPlan,
            AuditProgram,
        )

        auditor = User.objects.create_user(
            username='api.audit.lead@example.com',
            email='api.audit.lead@example.com',
            password='S3curePass!123',
        )
        responsible = User.objects.create_user(
            username='api.audit.resp@example.com',
            email='api.audit.resp@example.com',
            password='S3curePass!123',
        )
        other_owner = User.objects.create_user(
            username='api.audit.other@example.com',
            email='api.audit.other@example.com',
            password='S3curePass!123',
        )
        supplier, document = create_audit_context(auditor, suffix='001')
        other_supplier, _other_document = create_audit_context(other_owner, suffix='999')
        AuditProgram.objects.create(
            audit_type=AuditProgram.AuditType.INTERNAL,
            title='Programa secundario',
            year=timezone.localdate().year,
            scope='Outro escopo.',
            criteria='Outro critério.',
            owner=other_owner,
            starts_on=timezone.localdate(),
            ends_on=timezone.localdate() + timedelta(days=180),
        )
        client = APIClient()
        client.force_authenticate(auditor)

        program_response = client.post(
            '/api/audits/programs/',
            {
                'audit_type': AuditProgram.AuditType.SUPPLIER,
                'title': 'Programa API de fornecedores',
                'year': timezone.localdate().year,
                'scope': 'Fornecedores críticos.',
                'criteria': 'BPF e acordo técnico.',
                'owner': auditor.id,
                'starts_on': str(timezone.localdate()),
                'ends_on': str(timezone.localdate() + timedelta(days=365)),
            },
        )
        program_id = program_response.json()['id']
        invalid_plan_response = client.post(
            '/api/audits/plans/',
            {
                'program': program_id,
                'audit_type': AuditPlan.AuditType.SUPPLIER,
                'supplier': other_supplier.id,
                'title': 'Plano inválido',
                'scope': 'Fornecedor secundario.',
                'criteria': 'BPF.',
                'agenda': 'Agenda.',
                'lead_auditor': auditor.id,
                'auditee_name': 'Outro fornecedor',
                'area': 'QA',
                'scheduled_start': timezone.now().isoformat(),
                'scheduled_end': (timezone.now() + timedelta(hours=4)).isoformat(),
            },
        )
        plan_response = client.post(
            '/api/audits/plans/',
            {
                'program': program_id,
                'audit_type': AuditPlan.AuditType.SUPPLIER,
                'supplier': supplier.id,
                'title': 'Auditoria API de fornecedor',
                'scope': 'Sistema da qualidade do fornecedor.',
                'criteria': 'BPF e acordo técnico.',
                'agenda': 'Abertura, avaliação e encerramento.',
                'lead_auditor': auditor.id,
                'auditee_name': supplier.legal_name,
                'area': 'QA',
                'scheduled_start': timezone.now().isoformat(),
                'scheduled_end': (timezone.now() + timedelta(hours=4)).isoformat(),
            },
        )
        plan_id = plan_response.json()['id']
        checklist_response = client.post(
            '/api/audits/checklist-items/',
            {
                'audit': plan_id,
                'section': 'Sistema da Qualidade',
                'question': 'Controle de mudanças é efetivo?',
                'requirement_reference': 'BPF 1.4',
                'required': True,
            },
        )
        checklist_id = checklist_response.json()['id']
        submit_response = client.post(f'/api/audits/plans/{plan_id}/submit/')
        start_response = client.post(f'/api/audits/plans/{plan_id}/start/')
        answer_response = client.post(
            f'/api/audits/checklist-items/{checklist_id}/answer/',
            {'status': AuditChecklistItem.Status.NON_CONFORM, 'answer': 'Controle incompleto.'},
        )
        finding_response = client.post(
            '/api/audits/findings/',
            {
                'audit': plan_id,
                'checklist_item': checklist_id,
                'classification': AuditFinding.Classification.NONCONFORMITY,
                'criticality': AuditFinding.Criticality.MAJOR,
                'title': 'Não conformidade API',
                'description': 'Controle de mudanças incompleto.',
                'responsible': responsible.id,
                'due_date': str(timezone.localdate() + timedelta(days=30)),
            },
        )
        finding_id = finding_response.json()['id']
        complete_execution_response = client.post(
            f'/api/audits/plans/{plan_id}/complete_execution/'
        )
        evidence_response = client.post(
            '/api/audits/evidences/',
            {
                'audit': plan_id,
                'finding': finding_id,
                'title': 'Evidência API',
                'file_reference': 'auditorias/evidencia-api.pdf',
                'content_hash': 'sha256:evidenciaapi',
            },
        )
        action_response = client.post(
            '/api/audits/actions/',
            {
                'finding': finding_id,
                'title': 'Plano de ação API',
                'description': 'Corrigir controle de mudanças.',
                'responsible': responsible.id,
                'due_date': str(timezone.localdate() + timedelta(days=15)),
                'mandatory': True,
                'evidence_required': True,
            },
        )
        action_id = action_response.json()['id']
        client.force_authenticate(responsible)
        complete_action_response = client.post(
            f'/api/audits/actions/{action_id}/complete/',
            {
                'completion_notes': 'Ação concluída.',
                'evidence_reference': 'auditorias/acao-api.pdf',
                'content_hash': 'sha256:acaoapi',
            },
        )
        client.force_authenticate(auditor)
        link_response = client.post(
            '/api/audits/finding-links/',
            {
                'finding': finding_id,
                'link_type': AuditFindingLink.LinkType.SUPPLIER,
                'supplier': supplier.id,
                'reference_code': supplier.code,
            },
        )
        document_link_response = client.post(
            '/api/audits/finding-links/',
            {
                'finding': finding_id,
                'link_type': AuditFindingLink.LinkType.DOCUMENT,
                'document': document.id,
                'reference_code': document.code,
            },
        )
        report_response = client.post(
            '/api/audits/reports/',
            {
                'audit': plan_id,
                'executive_summary': 'Auditoria com uma não conformidade maior.',
                'conclusion': 'Plano de ação obrigatório definido.',
                'issued_by': auditor.id,
            },
        )
        report_id = report_response.json()['id']
        issue_report_response = client.post(f'/api/audits/reports/{report_id}/issue/')
        close_response = client.post(
            f'/api/audits/plans/{plan_id}/close/',
            {'summary': 'Auditoria encerrada com plano de ação.'},
        )
        list_response = client.get('/api/audits/plans/')

        assert program_response.status_code == 201
        assert invalid_plan_response.status_code == 201
        assert plan_response.status_code == 201
        assert checklist_response.status_code == 201
        assert submit_response.status_code == 200
        assert start_response.status_code == 200
        assert answer_response.status_code == 200
        assert finding_response.status_code == 201
        assert complete_execution_response.status_code == 200
        assert evidence_response.status_code == 201
        assert action_response.status_code == 201
        assert complete_action_response.status_code == 200
        assert link_response.status_code == 201
        assert document_link_response.status_code == 201
        assert report_response.status_code == 201
        assert issue_report_response.status_code == 200
        assert issue_report_response.json()['major_findings'] == 1
        assert close_response.status_code == 200
        assert close_response.json()['status'] == AuditPlan.Status.CLOSED
        assert 'Auditoria API de fornecedor' in {
            item['title'] for item in list_response.json()['results']
        }
