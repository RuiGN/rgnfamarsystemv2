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


def create_regulatory_context(owner, suffix='001'):
    unit = UnitOfMeasure.objects.create(code=f'UN-REG-{suffix}', name='Unidade', symbol='un')
    product = Product.objects.create(
        code=f'REG-PROD-{suffix}',
        description=f'Produto Regulatório {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    lot = StockLot.objects.create(
        product=product,
        lot_number=f'REG-LOTE-{suffix}',
        quality_status=StockQualityStatus.APPROVED,
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    supplier = BusinessPartner.objects.create(
        code=f'FOR-REG-{suffix}',
        legal_name=f'Fornecedor Regulatório {suffix}',
        partner_type=BusinessPartner.PartnerType.SUPPLIER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    manufacturer = BusinessPartner.objects.create(
        code=f'FAB-REG-{suffix}',
        legal_name=f'Fabricante Regulatório {suffix}',
        partner_type=BusinessPartner.PartnerType.MANUFACTURER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=365),
    )
    document = ControlledDocument.objects.create(
        document_type=ControlledDocument.DocumentType.DOSSIER,
        code=f'DOS-REG-{suffix}',
        title=f'Dossiê Regulatório {suffix}',
        area='Assuntos Regulatórios',
        version='1.0',
        effective_from=timezone.localdate(),
        owner=owner,
        content='Documento técnico regulatório.',
        change_summary='Emissão inicial.',
    )
    return product, lot, supplier, manufacturer, document


class RegulatoryModelTests(TestCase):
    def test_dossier_blocks_submission_and_closure_until_evidence_requirements_commitments_and_report(
        self,
    ):
        from regulatory.models import (
            RegulatoryCommitment,
            RegulatoryDossier,
            RegulatoryEvidence,
            RegulatoryPetition,
            RegulatoryProduct,
            RegulatoryReport,
            RegulatoryRequirement,
        )

        owner = User.objects.create_user(
            username='reg.owner@example.com',
            email='reg.owner@example.com',
            password='S3curePass!123',
        )
        reviewer = User.objects.create_user(
            username='reg.reviewer@example.com',
            email='reg.reviewer@example.com',
            password='S3curePass!123',
        )
        product, _lot, _supplier, _manufacturer, _document = create_regulatory_context(owner)
        regulatory_product = RegulatoryProduct.objects.create(
            product=product,
            presentation='Comprimido revestido 500 mg x 30',
            registration_holder='RGN Farma',
            therapeutic_class='Antibiótico',
            dosage_form='Comprimido revestido',
            strength='500 mg',
            route='Oral',
            responsible=owner,
        )
        dossier = RegulatoryDossier.objects.create(
            regulatory_product=regulatory_product,
            dossier_type=RegulatoryDossier.DossierType.REGISTRATION,
            title='Registro inicial de produto acabado',
            authority='ANVISA',
            subject='Solicitação de registro sanitário.',
            responsible=owner,
            due_date=timezone.localdate() + timedelta(days=90),
        )
        petition = RegulatoryPetition.objects.create(
            dossier=dossier,
            petition_type=RegulatoryPetition.PetitionType.INITIAL_REGISTRATION,
            subject='Petição de registro inicial',
            responsible=owner,
            response_due_date=timezone.localdate() + timedelta(days=120),
        )
        requirement = RegulatoryRequirement.objects.create(
            dossier=dossier,
            petition=petition,
            description='Apresentar complemento de validação de processo.',
            received_at=timezone.localdate(),
            response_due_date=timezone.localdate() + timedelta(days=30),
            responsible=owner,
        )
        commitment = RegulatoryCommitment.objects.create(
            dossier=dossier,
            description='Protocolar relatório de estabilidade de acompanhamento.',
            due_date=timezone.localdate() + timedelta(days=45),
            responsible=owner,
        )

        with pytest.raises(ValidationError) as no_evidence:
            dossier.submit(user=owner)

        RegulatoryEvidence.objects.create(
            dossier=dossier,
            title='Dossiê técnico inicial',
            file_reference='regulatorio/dossie-tecnico.pdf',
            content_hash='sha256:dossietecnico',
            uploaded_by=owner,
        )
        dossier.submit(user=owner)
        petition.submit(protocol_number='25351.000001/2026-01', user=owner)

        with pytest.raises(ValidationError) as no_requirement:
            dossier.close(summary='Tentativa sem exigência respondida.', user=reviewer)

        requirement.answer(
            response_summary='Complemento de validação enviado à autoridade.',
            evidence_reference='regulatorio/resposta-exigencia.pdf',
            content_hash='sha256:respostaexigencia',
            user=owner,
        )

        with pytest.raises(ValidationError) as no_commitment:
            dossier.close(summary='Tentativa sem compromisso concluído.', user=reviewer)

        commitment.complete(
            completion_summary='Relatório de estabilidade protocolado.',
            evidence_reference='regulatorio/estabilidade.pdf',
            content_hash='sha256:estabilidade',
            user=owner,
        )

        with pytest.raises(ValidationError) as no_report:
            dossier.close(summary='Tentativa sem relatório gerado.', user=reviewer)

        report = RegulatoryReport.objects.create(
            dossier=dossier,
            report_type=RegulatoryReport.ReportType.ANVISA_DOSSIER,
            title='Dossiê consolidado para ANVISA',
        )
        report.generate(user=reviewer, content_reference='regulatorio/dossie-consolidado.pdf')
        dossier.close(
            summary='Dossiê encerrado com protocolo e pendências tratadas.', user=reviewer
        )

        dossier.refresh_from_db()
        report.refresh_from_db()
        assert 'evidences' in no_evidence.value.message_dict
        assert 'requirements' in no_requirement.value.message_dict
        assert 'commitments' in no_commitment.value.message_dict
        assert 'reports' in no_report.value.message_dict
        assert dossier.status == RegulatoryDossier.Status.CLOSED
        assert dossier.closed_by == reviewer
        assert petition.status == RegulatoryPetition.Status.SUBMITTED
        assert requirement.status == RegulatoryRequirement.Status.ANSWERED
        assert commitment.status == RegulatoryCommitment.Status.COMPLETED
        assert report.status == RegulatoryReport.Status.GENERATED
        assert report.total_requirements == 1
        assert report.open_commitments == 0
        assert report.evidence_count == 1

    def test_regulatory_supports_lifecycle_types_links_and_alert_generation(self):
        from regulatory.models import (
            RegulatoryAlert,
            RegulatoryCommitment,
            RegulatoryDossier,
            RegulatoryLink,
            RegulatoryPetition,
            RegulatoryProduct,
            RegulatoryRegistration,
            RegulatoryRequirement,
        )

        owner = User.objects.create_user(
            username='reg.alert.owner@example.com',
            email='reg.alert.owner@example.com',
            password='S3curePass!123',
        )
        product, _lot, _supplier, _manufacturer, _document = create_regulatory_context(owner)
        regulatory_product = RegulatoryProduct.objects.create(
            product=product,
            presentation='Solução oral 10 mg/mL x 100 mL',
            registration_holder='RGN Farma',
            therapeutic_class='Analgésico',
            dosage_form='Solução oral',
            strength='10 mg/mL',
            route='Oral',
            responsible=owner,
        )
        dossier = RegulatoryDossier.objects.create(
            regulatory_product=regulatory_product,
            dossier_type=RegulatoryDossier.DossierType.RENEWAL,
            title='Renovação de registro',
            authority='ANVISA',
            subject='Renovação quinquenal.',
            responsible=owner,
            due_date=timezone.localdate() + timedelta(days=60),
        )
        RegulatoryRegistration.objects.create(
            regulatory_product=regulatory_product,
            dossier=dossier,
            registration_number='MS-1.2345.0001',
            status=RegulatoryRegistration.Status.ACTIVE,
            valid_from=timezone.localdate() - timedelta(days=365),
            valid_until=timezone.localdate() + timedelta(days=20),
            next_renewal_due_date=timezone.localdate() + timedelta(days=15),
            responsible=owner,
        )
        petition = RegulatoryPetition.objects.create(
            dossier=dossier,
            petition_type=RegulatoryPetition.PetitionType.RENEWAL,
            subject='Petição de renovação',
            responsible=owner,
            response_due_date=timezone.localdate() + timedelta(days=10),
            status=RegulatoryPetition.Status.SUBMITTED,
            protocol_number='25351.000002/2026-01',
            submitted_by=owner,
            submitted_at=timezone.now(),
        )
        RegulatoryRequirement.objects.create(
            dossier=dossier,
            petition=petition,
            description='Exigência para complemento de bula.',
            received_at=timezone.localdate(),
            response_due_date=timezone.localdate() + timedelta(days=5),
            responsible=owner,
        )
        RegulatoryCommitment.objects.create(
            dossier=dossier,
            description='Compromisso de relatório pós-registro.',
            due_date=timezone.localdate() - timedelta(days=1),
            responsible=owner,
        )

        generated = RegulatoryAlert.generate_all()

        assert {
            RegulatoryDossier.DossierType.REGISTRATION,
            RegulatoryDossier.DossierType.POST_REGISTRATION,
            RegulatoryDossier.DossierType.RENEWAL,
            RegulatoryDossier.DossierType.VARIATION,
            RegulatoryDossier.DossierType.INSPECTION,
        }.issubset(set(RegulatoryDossier.DossierType.values))
        assert {
            RegulatoryPetition.PetitionType.INITIAL_REGISTRATION,
            RegulatoryPetition.PetitionType.POST_REGISTRATION,
            RegulatoryPetition.PetitionType.RENEWAL,
            RegulatoryPetition.PetitionType.REQUIREMENT_RESPONSE,
        }.issubset(set(RegulatoryPetition.PetitionType.values))
        assert {
            RegulatoryLink.LinkType.PRODUCT,
            RegulatoryLink.LinkType.PRESENTATION,
            RegulatoryLink.LinkType.LOT,
            RegulatoryLink.LinkType.DOCUMENT,
            RegulatoryLink.LinkType.CHANGE,
            RegulatoryLink.LinkType.DEVIATION,
            RegulatoryLink.LinkType.CAPA,
            RegulatoryLink.LinkType.STUDY,
            RegulatoryLink.LinkType.SUPPLIER,
            RegulatoryLink.LinkType.MANUFACTURER,
        }.issubset(set(RegulatoryLink.LinkType.values))
        assert generated == 5
        assert set(RegulatoryAlert.objects.values_list('alert_type', flat=True)) == {
            RegulatoryAlert.AlertType.REGISTRATION_EXPIRY,
            RegulatoryAlert.AlertType.RENEWAL_DUE,
            RegulatoryAlert.AlertType.COMMITMENT_DUE,
            RegulatoryAlert.AlertType.REQUIREMENT_DUE,
            RegulatoryAlert.AlertType.RESPONSE_DUE,
        }


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestRegulatoryApi:
    def test_regulatory_api_uses_global_scope_and_executes_required_workflow(self):
        from regulatory.models import (
            RegulatoryDossier,
            RegulatoryProduct,
            RegulatoryReport,
        )

        owner = User.objects.create_user(
            username='api.reg.owner@example.com',
            email='api.reg.owner@example.com',
            password='S3curePass!123',
        )
        User.objects.create_user(
            username='api.reg.reviewer@example.com',
            email='api.reg.reviewer@example.com',
            password='S3curePass!123',
        )
        other_owner = User.objects.create_user(
            username='api.reg.other@example.com',
            email='api.reg.other@example.com',
            password='S3curePass!123',
        )
        product, lot, supplier, manufacturer, document = create_regulatory_context(
            owner, suffix='001'
        )
        other_product, _other_lot, _other_supplier, _other_manufacturer, _other_document = (
            create_regulatory_context(other_owner, suffix='999')
        )
        other_regulatory_product = RegulatoryProduct.objects.create(
            product=other_product,
            presentation='Produto secundário',
            registration_holder='Outra empresa',
            therapeutic_class='Outra classe',
            dosage_form='Comprimido',
            strength='10 mg',
            route='Oral',
            responsible=other_owner,
        )
        RegulatoryDossier.objects.create(
            regulatory_product=other_regulatory_product,
            dossier_type=RegulatoryDossier.DossierType.REGISTRATION,
            title='Dossiê secundário',
            authority='ANVISA',
            subject='Outro assunto.',
            responsible=other_owner,
            due_date=timezone.localdate() + timedelta(days=30),
        )

        client = APIClient()
        client.force_authenticate(owner)

        product_response = client.post(
            '/api/regulatory/products/',
            {
                'product': product.id,
                'presentation': 'Comprimido revestido 500 mg x 30',
                'registration_holder': 'RGN Farma',
                'therapeutic_class': 'Antibiótico',
                'dosage_form': 'Comprimido revestido',
                'strength': '500 mg',
                'route': 'Oral',
                'responsible': owner.id,
            },
        )
        regulatory_product_id = product_response.json()['id']
        dossier_response = client.post(
            '/api/regulatory/dossiers/',
            {
                'regulatory_product': regulatory_product_id,
                'dossier_type': RegulatoryDossier.DossierType.REGISTRATION,
                'title': 'Dossiê API de registro inicial',
                'authority': 'ANVISA',
                'subject': 'Registro sanitário de produto acabado.',
                'responsible': owner.id,
                'due_date': str(timezone.localdate() + timedelta(days=90)),
            },
        )
        dossier_id = dossier_response.json()['id']
        invalid_link_response = client.post(
            '/api/regulatory/links/',
            {
                'dossier': dossier_id,
                'link_type': 'product',
                'product': other_product.id,
                'description': 'Produto secundário pode ser vinculado no escopo global.',
            },
        )
        link_payloads = [
            {
                'link_type': 'product',
                'product': product.id,
                'description': 'Produto objeto do registro.',
            },
            {
                'link_type': 'lot',
                'stock_lot': lot.id,
                'description': 'Lote piloto usado no dossiê.',
            },
            {
                'link_type': 'document',
                'document': document.id,
                'description': 'Documento técnico do dossiê.',
            },
            {
                'link_type': 'supplier',
                'partner': supplier.id,
                'description': 'Fornecedor qualificado.',
            },
            {
                'link_type': 'manufacturer',
                'partner': manufacturer.id,
                'description': 'Fabricante qualificado.',
            },
        ]
        link_responses = [
            client.post(
                '/api/regulatory/links/',
                {'dossier': dossier_id, **payload},
            )
            for payload in link_payloads
        ]
        evidence_response = client.post(
            '/api/regulatory/evidences/',
            {
                'dossier': dossier_id,
                'title': 'Dossiê técnico API',
                'file_reference': 'regulatorio/api-dossie.pdf',
                'content_hash': 'sha256:apidossie',
            },
        )
        submit_response = client.post(f'/api/regulatory/dossiers/{dossier_id}/submit/')
        petition_response = client.post(
            '/api/regulatory/petitions/',
            {
                'dossier': dossier_id,
                'petition_type': 'initial_registration',
                'subject': 'Petição API de registro',
                'responsible': owner.id,
                'response_due_date': str(timezone.localdate() + timedelta(days=120)),
            },
        )
        petition_id = petition_response.json()['id']
        petition_submit_response = client.post(
            f'/api/regulatory/petitions/{petition_id}/submit/',
            {'protocol_number': '25351.000003/2026-01'},
        )
        requirement_response = client.post(
            '/api/regulatory/requirements/',
            {
                'dossier': dossier_id,
                'petition': petition_id,
                'description': 'Complementar validação API.',
                'received_at': str(timezone.localdate()),
                'response_due_date': str(timezone.localdate() + timedelta(days=30)),
                'responsible': owner.id,
            },
        )
        requirement_id = requirement_response.json()['id']
        requirement_answer_response = client.post(
            f'/api/regulatory/requirements/{requirement_id}/answer/',
            {
                'response_summary': 'Complemento protocolado.',
                'evidence_reference': 'regulatorio/api-resposta.pdf',
                'content_hash': 'sha256:apiresposta',
            },
        )
        commitment_response = client.post(
            '/api/regulatory/commitments/',
            {
                'dossier': dossier_id,
                'description': 'Compromisso API de estabilidade.',
                'due_date': str(timezone.localdate() + timedelta(days=45)),
                'responsible': owner.id,
            },
        )
        commitment_id = commitment_response.json()['id']
        commitment_complete_response = client.post(
            f'/api/regulatory/commitments/{commitment_id}/complete/',
            {
                'completion_summary': 'Compromisso concluído.',
                'evidence_reference': 'regulatorio/api-compromisso.pdf',
                'content_hash': 'sha256:apicompromisso',
            },
        )
        report_response = client.post(
            '/api/regulatory/reports/',
            {
                'dossier': dossier_id,
                'report_type': RegulatoryReport.ReportType.ANVISA_DOSSIER,
                'title': 'Dossiê API consolidado',
            },
        )
        report_id = report_response.json()['id']
        report_generate_response = client.post(
            f'/api/regulatory/reports/{report_id}/generate/',
            {'content_reference': 'regulatorio/api-dossie-consolidado.pdf'},
        )
        close_response = client.post(
            f'/api/regulatory/dossiers/{dossier_id}/close/',
            {'summary': 'Dossiê API encerrado.'},
        )
        list_response = client.get('/api/regulatory/dossiers/')

        assert product_response.status_code == 201
        assert dossier_response.status_code == 201
        assert invalid_link_response.status_code == 201
        assert all(response.status_code == 201 for response in link_responses)
        assert evidence_response.status_code == 201
        assert submit_response.status_code == 200
        assert petition_response.status_code == 201
        assert petition_submit_response.status_code == 200
        assert requirement_response.status_code == 201
        assert requirement_answer_response.status_code == 200
        assert commitment_response.status_code == 201
        assert commitment_complete_response.status_code == 200
        assert report_response.status_code == 201
        assert report_generate_response.status_code == 200
        assert close_response.status_code == 200
        assert close_response.json()['status'] == RegulatoryDossier.Status.CLOSED
        assert list_response.status_code == 200
        assert {item['title'] for item in list_response.json()['results']} == {
            'Dossiê API de registro inicial',
            'Dossiê secundário',
        }
