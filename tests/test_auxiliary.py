import pytest

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from base.ui.registry import get_modules


@pytest.mark.legacy_api_permissions
class AuxiliaryCatalogTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='auxiliary@example.com',
            email='auxiliary@example.com',
            password='S3curePass!123',
        )

    def test_auxiliary_catalog_codes_are_globally_unique(self):
        from auxiliary.models import BusinessArea, Currency

        area = BusinessArea.objects.create(code='QA', name='Garantia da Qualidade')
        BusinessArea.objects.create(code='QA-GO', name='Qualidade Goiania')
        Currency.objects.create(code='BRL', name='Real brasileiro', numeric_code='986')

        assert str(area) == 'QA - Garantia da Qualidade'
        assert BusinessArea.objects.filter(code__startswith='QA').count() == 2

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                BusinessArea.objects.create(code='QA', name='Duplicada')

    def test_auxiliary_module_is_registered_for_generic_crud(self):
        modules = {module.slug: module for module in get_modules()}

        assert 'auxiliary' in modules
        labels = [resource.label for resource in modules['auxiliary'].resources]
        assert 'Áreas operacionais' in labels
        assert 'Moedas' in labels
        assert 'Módulos do sistema' in labels

    def test_auxiliary_module_uses_existing_generic_templates(self):
        self.client.force_login(self.user)

        response = self.client.get('/app/auxiliary/')

        assert response.status_code == 200
        content = response.content.decode()
        assert 'Auxiliares' in content
        assert 'Áreas operacionais' in content
        assert 'Condições comerciais' in content

    def test_high_redundancy_models_expose_auxiliary_foreign_keys(self):
        from ai_agents.models import AIAgentProfile, AIAgentRun, AIInsightSuggestion
        from audits.models import AuditFinding, AuditPlan
        from changes.models import ChangeAssessment
        from compliance.models import (
            ComplianceChecklistItem,
            CriticalActionExecution,
            RecordStatusHistory,
            TransversalRequirementPolicy,
        )
        from crm.models import CustomerComplaint, CustomerContact
        from deviations.models import QualityEvent
        from documents.models import ControlledDocument
        from files.models import ProtectedFile, ProtectedFileAccessRule
        from fiscal.models import FiscalCompany, FiscalMunicipality
        from governance.models import (
            GovernanceAuditLog,
            GovernanceCatalogItem,
            GovernanceParameter,
        )
        from maintenance.models import EquipmentAsset
        from masters.models import BusinessPartner
        from pharmacovigilance.models import PharmacovigilanceCase
        from procurement.models import PurchaseOrder, SupplierQualificationEvent, SupplierQuotation
        from recalls.models import MarketComplaint, RecallCampaign
        from reports.models import DashboardWidget, DashboardWorkspace, ReportDefinition
        from risks.models import RiskAlert, RiskRecord
        from training.models import (
            CriticalActivityRule as WorkforceCriticalActivityRule,
            JobPosition,
            TrainingIndicatorReport,
            TrainingRequirement as WorkforceTrainingRequirement,
            WorkFunction,
        )
        from qa.models import (
            CriticalActivityRule as QACriticalActivityRule,
            TrainingRequirement as QATrainingRequirement,
        )
        from regulatory.models import RegulatoryAlert
        from workflow.models import (
            ApprovalQueue,
            ApprovalTask,
            AsyncJobStatus,
            WorkflowDelegation,
            WorkflowNotification,
        )

        expected_fields = {
            ControlledDocument: ['area_ref'],
            QualityEvent: ['area_ref', 'severity_ref', 'criticality_ref'],
            AuditPlan: ['area_ref'],
            AuditFinding: ['criticality_ref'],
            EquipmentAsset: ['area_ref'],
            QATrainingRequirement: ['area_ref', 'process_ref', 'role_ref'],
            QACriticalActivityRule: ['area_ref', 'process_ref', 'role_ref'],
            JobPosition: ['area_ref', 'department_ref'],
            WorkFunction: ['area_ref', 'process_ref'],
            WorkforceTrainingRequirement: ['area_ref', 'process_ref'],
            WorkforceCriticalActivityRule: ['area_ref', 'process_ref'],
            TrainingIndicatorReport: ['area_ref', 'process_ref'],
            RiskRecord: ['process_ref'],
            ChangeAssessment: ['department_ref'],
            BusinessPartner: ['state_ref', 'city_ref'],
            FiscalCompany: ['state_ref', 'city_ref'],
            FiscalMunicipality: ['state_ref', 'city_ref'],
            PharmacovigilanceCase: ['country_ref', 'severity_ref'],
            SupplierQuotation: ['currency_ref', 'payment_term_ref', 'delivery_term_ref'],
            PurchaseOrder: ['currency_ref', 'payment_term_ref', 'delivery_term_ref'],
            ProtectedFile: ['source_module_ref', 'source_model_ref', 'criticality_ref'],
            ProtectedFileAccessRule: ['source_module_ref', 'source_model_ref'],
            WorkflowNotification: ['source_module_ref', 'source_model_ref', 'criticality_ref'],
            ApprovalQueue: ['module_ref', 'area_ref', 'role_ref', 'criticality_ref'],
            ApprovalTask: ['source_module_ref', 'source_model_ref', 'area_ref', 'criticality_ref'],
            WorkflowDelegation: ['module_ref'],
            AsyncJobStatus: ['source_module_ref', 'source_model_ref'],
            AIAgentProfile: ['source_module_ref'],
            AIAgentRun: ['source_module_ref', 'source_model_ref'],
            AIInsightSuggestion: ['source_module_ref', 'source_model_ref'],
            TransversalRequirementPolicy: ['source_module_ref'],
            RecordStatusHistory: ['source_module_ref', 'target_model_ref'],
            CriticalActionExecution: ['source_module_ref', 'target_model_ref'],
            ComplianceChecklistItem: ['source_module_ref'],
            ReportDefinition: ['module_ref'],
            DashboardWorkspace: ['module_ref', 'role_ref'],
            DashboardWidget: ['module_ref'],
            GovernanceParameter: ['module_ref'],
            GovernanceCatalogItem: ['module_ref'],
            GovernanceAuditLog: ['module_ref', 'target_model_ref', 'severity_ref'],
            SupplierQualificationEvent: ['severity_ref'],
            CustomerContact: ['role_ref'],
            CustomerComplaint: ['severity_ref'],
            RiskAlert: ['severity_ref'],
            RegulatoryAlert: ['severity_ref'],
            MarketComplaint: ['criticality_ref'],
            RecallCampaign: ['criticality_ref'],
        }

        for model, field_names in expected_fields.items():
            actual = {field.name for field in model._meta.get_fields()}
            for field_name in field_names:
                assert field_name in actual, f'{model._meta.label}.{field_name} ausente'
