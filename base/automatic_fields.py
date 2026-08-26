from types import MappingProxyType


AUTOMATIC_CODE_MODELS = frozenset(
    {
        'ai_agents.AIAgentProfile',
        'auxiliary.BusinessArea',
        'auxiliary.BusinessProcess',
        'auxiliary.CatalogType',
        'auxiliary.CatalogValue',
        'auxiliary.CommercialTerm',
        'auxiliary.Department',
        'auxiliary.ImpactLevel',
        'auxiliary.OrganizationalRole',
        'auxiliary.SystemModel',
        'auxiliary.SystemModule',
        'costing.CostElement',
        'crm.Campaign',
        'crm.CustomerGroup',
        'crm.SalesChannel',
        'crm.SalesRepresentative',
        'documents.ControlledDocument',
        'finance.FinancialAccount',
        'finance.FinancialCategory',
        'formulations.ManufacturingRoute',
        'formulations.MasterFormula',
        'masters.BusinessPartner',
        'masters.MasterCategory',
        'masters.Product',
        'masters.Site',
        'masters.StorageLocation',
        'masters.Warehouse',
        'planning.CapacityResource',
        'planning.MasterProductionSchedule',
        'qa.TrainingRequirement',
        'reports.DashboardWorkspace',
        'reports.ReportDefinition',
        'training.Competency',
        'training.JobPosition',
        'training.TrainingRequirement',
        'training.WorkFunction',
        'workflow.ApprovalQueue',
    }
)


AUTOMATIC_IDENTIFIER_FIELDS = MappingProxyType(
    {
        'ai_agents.AIAgentRun': ('run_number',),
        'audits.AuditPlan': ('audit_number',),
        'audits.AuditProgram': ('program_number',),
        'capa.CapaRecord': ('capa_number',),
        'changes.ChangeControl': ('change_number',),
        'crm.SalesContract': ('contract_number',),
        'crm.SalesOrder': ('order_number',),
        'crm.SalesProposal': ('proposal_number',),
        'deviations.QualityEvent': ('event_number',),
        'files.ProtectedFile': ('file_number',),
        'finance.FinancialTitle': ('title_number',),
        'inventory.StockMovement': ('movement_number',),
        'maintenance.EquipmentAsset': ('asset_code',),
        'maintenance.MaintenanceOrder': ('order_number',),
        'procurement.PurchaseOrder': ('order_number',),
        'procurement.PurchaseReceipt': ('receipt_number',),
        'procurement.PurchaseRequisition': ('requisition_number',),
        'procurement.QuotationRequest': ('rfq_number',),
        'production.ProductionOrder': ('batch_number',),
        'qa.LotRelease': ('release_number',),
        'qa.QAReview': ('review_number',),
        'qa.QualityBlock': ('block_number',),
        'quality.LaboratoryInvestigation': ('investigation_number',),
        'quality.QualityAnalysis': ('analysis_number',),
        'quality.QualityDocument': ('document_number',),
        'quality.QualitySample': ('sample_number',),
        'recalls.MarketComplaint': ('complaint_number',),
        'recalls.ProductReturn': ('return_number',),
        'recalls.RecallCampaign': ('campaign_number',),
        'reports.ReportExecution': ('execution_number',),
        'risks.RiskRecord': ('risk_number',),
        'training.TrainingEnrollment': ('enrollment_number', 'certificate_number'),
        'training.TrainingSession': ('session_number',),
        'workflow.ApprovalTask': ('task_number',),
        'workflow.AsyncJobStatus': ('job_number',),
    }
)


def automatic_generated_fields(model):
    fields = []
    if model._meta.label in AUTOMATIC_CODE_MODELS:
        fields.append('code')
    fields.extend(AUTOMATIC_IDENTIFIER_FIELDS.get(model._meta.label, ()))
    return tuple(fields)
