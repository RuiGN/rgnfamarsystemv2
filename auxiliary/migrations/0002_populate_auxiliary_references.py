import hashlib
import re
import unicodedata

from django.db import migrations


def _clean(value):
    return str(value or '').strip()


def _code(value, prefix='', max_length=80):
    value = _clean(value)
    ascii_value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    normalized = re.sub(r'[^A-Za-z0-9]+', '_', ascii_value).strip('_').upper()
    if not normalized:
        normalized = hashlib.sha1(value.encode('utf-8'), usedforsecurity=False).hexdigest()[
            :12
        ].upper()
    if prefix:
        normalized = f'{prefix}_{normalized}'
    return normalized[:max_length]


def _catalog(apps, model_name, tenant_id, value, **defaults):
    value = _clean(value)
    if not value:
        return None
    model = apps.get_model('auxiliary', model_name)
    code = defaults.pop('code', _code(value))
    obj, _created = model.objects.get_or_create(
        tenant_id=tenant_id,
        code=code,
        defaults={'name': defaults.pop('name', value), **defaults},
    )
    return obj


def _module(apps, tenant_id, value):
    value = _clean(value)
    if not value:
        return None
    return _catalog(apps, 'SystemModule', tenant_id, value, code=_code(value), app_label=value, menu_label=value)


def _system_model(apps, tenant_id, model_value, module_value=''):
    model_value = _clean(model_value)
    if not model_value:
        return None
    module = _module(apps, tenant_id, module_value)
    code = _code(f'{module_value}_{model_value}' if module_value else model_value)
    return _catalog(
        apps,
        'SystemModel',
        tenant_id,
        model_value,
        code=code,
        module_id=getattr(module, 'pk', None),
        app_label=_clean(module_value),
        model_name=model_value,
    )


def _impact(apps, tenant_id, value, level_type):
    value = _clean(value)
    if not value:
        return None
    weights = {
        'low': 1,
        'minor': 1,
        'medium': 2,
        'major': 3,
        'high': 3,
        'critical': 4,
        'error': 4,
        'warning': 2,
        'info': 1,
    }
    return _catalog(
        apps,
        'ImpactLevel',
        tenant_id,
        value,
        code=_code(value, prefix=level_type),
        level_type=level_type,
        weight=weights.get(value.lower(), 0),
    )


def _term(apps, tenant_id, value, term_type):
    value = _clean(value)
    if not value:
        return None
    return _catalog(apps, 'CommercialTerm', tenant_id, value, code=_code(value, prefix=term_type), term_type=term_type)


def _set_fk_from_text(apps, model_label, text_field, fk_field, catalog_model, **defaults):
    app_label, model_name = model_label.split('.')
    model = apps.get_model(app_label, model_name)
    for obj in model.objects.exclude(**{text_field: ''}).iterator():
        catalog = _catalog(apps, catalog_model, obj.tenant_id, getattr(obj, text_field), **defaults)
        if catalog:
            model.objects.filter(pk=obj.pk).update(**{f'{fk_field}_id': catalog.pk})


def _populate_area_process_role_department(apps):
    for model_label, text_field, fk_field in [
        ('documents.ControlledDocument', 'area', 'area_ref'),
        ('deviations.QualityEvent', 'area', 'area_ref'),
        ('audits.AuditPlan', 'area', 'area_ref'),
        ('maintenance.EquipmentAsset', 'area', 'area_ref'),
        ('qa.TrainingRequirement', 'area', 'area_ref'),
        ('qa.CriticalActivityRule', 'area', 'area_ref'),
        ('training.JobPosition', 'area', 'area_ref'),
        ('training.WorkFunction', 'area', 'area_ref'),
        ('training.TrainingRequirement', 'area', 'area_ref'),
        ('training.CriticalActivityRule', 'area', 'area_ref'),
        ('training.TrainingIndicatorReport', 'area', 'area_ref'),
        ('workflow.ApprovalQueue', 'area', 'area_ref'),
        ('workflow.ApprovalTask', 'area', 'area_ref'),
    ]:
        _set_fk_from_text(apps, model_label, text_field, fk_field, 'BusinessArea')

    for model_label, text_field, fk_field in [
        ('qa.TrainingRequirement', 'process', 'process_ref'),
        ('qa.CriticalActivityRule', 'process', 'process_ref'),
        ('training.WorkFunction', 'process', 'process_ref'),
        ('training.TrainingRequirement', 'process', 'process_ref'),
        ('training.CriticalActivityRule', 'process', 'process_ref'),
        ('training.TrainingIndicatorReport', 'process', 'process_ref'),
        ('risks.RiskRecord', 'process_area', 'process_ref'),
    ]:
        _set_fk_from_text(apps, model_label, text_field, fk_field, 'BusinessProcess')

    for model_label, text_field, fk_field in [
        ('training.JobPosition', 'department', 'department_ref'),
        ('changes.ChangeAssessment', 'department', 'department_ref'),
    ]:
        _set_fk_from_text(apps, model_label, text_field, fk_field, 'Department')

    for model_label, text_field, fk_field in [
        ('qa.TrainingRequirement', 'required_role', 'role_ref'),
        ('qa.CriticalActivityRule', 'required_role', 'role_ref'),
        ('crm.CustomerContact', 'role', 'role_ref'),
        ('reports.DashboardWorkspace', 'profile_role', 'role_ref'),
        ('workflow.ApprovalQueue', 'profile_role', 'role_ref'),
    ]:
        _set_fk_from_text(apps, model_label, text_field, fk_field, 'OrganizationalRole')


def _populate_locations(apps):
    for model_label, state_field, city_field in [
        ('masters.BusinessPartner', 'state', 'city'),
        ('fiscal.FiscalCompany', 'state', 'city'),
    ]:
        app_label, model_name = model_label.split('.')
        model = apps.get_model(app_label, model_name)
        for obj in model.objects.all().iterator():
            state = _catalog(
                apps,
                'StateProvince',
                obj.tenant_id,
                getattr(obj, state_field),
                code=_code(getattr(obj, state_field), max_length=16),
                abbreviation=_clean(getattr(obj, state_field))[:16],
            )
            city = None
            city_value = _clean(getattr(obj, city_field))
            if city_value:
                city = _catalog(
                    apps,
                    'City',
                    obj.tenant_id,
                    city_value,
                    code=_code(f'{getattr(obj, state_field)}_{city_value}'),
                    state_id=getattr(state, 'pk', None),
                )
            model.objects.filter(pk=obj.pk).update(
                state_ref_id=getattr(state, 'pk', None),
                city_ref_id=getattr(city, 'pk', None),
            )

    municipality = apps.get_model('fiscal', 'FiscalMunicipality')
    for obj in municipality.objects.all().iterator():
        state = _catalog(
            apps,
            'StateProvince',
            obj.tenant_id,
            obj.state,
            code=_code(obj.state, max_length=16),
            abbreviation=_clean(obj.state)[:16],
        )
        city = _catalog(
            apps,
            'City',
            obj.tenant_id,
            obj.name,
            code=_code(obj.ibge_code or f'{obj.state}_{obj.name}'),
            state_id=getattr(state, 'pk', None),
            ibge_code=obj.ibge_code,
        )
        municipality.objects.filter(pk=obj.pk).update(
            state_ref_id=getattr(state, 'pk', None),
            city_ref_id=getattr(city, 'pk', None),
        )

    case = apps.get_model('pharmacovigilance', 'PharmacovigilanceCase')
    for obj in case.objects.exclude(country='').iterator():
        country = _catalog(apps, 'Country', obj.tenant_id, obj.country)
        case.objects.filter(pk=obj.pk).update(country_ref_id=getattr(country, 'pk', None))


def _populate_commercial(apps):
    for model_label in ['procurement.SupplierQuotation', 'procurement.PurchaseOrder']:
        app_label, model_name = model_label.split('.')
        model = apps.get_model(app_label, model_name)
        for obj in model.objects.all().iterator():
            currency = _catalog(apps, 'Currency', obj.tenant_id, obj.currency, code=_code(obj.currency, max_length=3))
            payment_term = _term(apps, obj.tenant_id, obj.payment_terms, 'payment')
            delivery_term = _term(apps, obj.tenant_id, obj.delivery_terms, 'delivery')
            model.objects.filter(pk=obj.pk).update(
                currency_ref_id=getattr(currency, 'pk', None),
                payment_term_ref_id=getattr(payment_term, 'pk', None),
                delivery_term_ref_id=getattr(delivery_term, 'pk', None),
            )


def _populate_system_references(apps):
    for model_label, module_field, module_fk in [
        ('ai_agents.AIAgentProfile', 'source_module', 'source_module_ref'),
        ('ai_agents.AIAgentRun', 'source_module', 'source_module_ref'),
        ('ai_agents.AIInsightSuggestion', 'source_module', 'source_module_ref'),
        ('compliance.TransversalRequirementPolicy', 'source_module', 'source_module_ref'),
        ('compliance.RecordStatusHistory', 'source_module', 'source_module_ref'),
        ('compliance.CriticalActionExecution', 'source_module', 'source_module_ref'),
        ('compliance.ComplianceChecklistItem', 'source_module', 'source_module_ref'),
        ('files.ProtectedFile', 'source_module', 'source_module_ref'),
        ('files.ProtectedFileAccessRule', 'source_module', 'source_module_ref'),
        ('workflow.WorkflowNotification', 'source_module', 'source_module_ref'),
        ('workflow.ApprovalTask', 'source_module', 'source_module_ref'),
        ('workflow.AsyncJobStatus', 'source_module', 'source_module_ref'),
        ('reports.ReportDefinition', 'module', 'module_ref'),
        ('reports.DashboardWorkspace', 'module', 'module_ref'),
        ('reports.DashboardWidget', 'module', 'module_ref'),
        ('workflow.ApprovalQueue', 'module', 'module_ref'),
        ('workflow.WorkflowDelegation', 'module', 'module_ref'),
        ('governance.TenantModuleSetting', 'module', 'module_ref'),
        ('governance.GovernanceParameter', 'module', 'module_ref'),
        ('governance.GovernanceCatalogItem', 'module', 'module_ref'),
        ('governance.GovernanceAuditLog', 'module', 'module_ref'),
    ]:
        app_label, model_name = model_label.split('.')
        model = apps.get_model(app_label, model_name)
        for obj in model.objects.exclude(**{module_field: ''}).iterator():
            module = _module(apps, obj.tenant_id, getattr(obj, module_field))
            model.objects.filter(pk=obj.pk).update(**{f'{module_fk}_id': getattr(module, 'pk', None)})

    for model_label, module_field, model_field, model_fk in [
        ('ai_agents.AIAgentRun', 'source_module', 'source_model', 'source_model_ref'),
        ('ai_agents.AIInsightSuggestion', 'source_module', 'source_model', 'source_model_ref'),
        ('files.ProtectedFile', 'source_module', 'source_model', 'source_model_ref'),
        ('files.ProtectedFileAccessRule', 'source_module', 'source_model', 'source_model_ref'),
        ('workflow.WorkflowNotification', 'source_module', 'source_model', 'source_model_ref'),
        ('workflow.ApprovalTask', 'source_module', 'source_model', 'source_model_ref'),
        ('workflow.AsyncJobStatus', 'source_module', 'source_model', 'source_model_ref'),
        ('compliance.RecordStatusHistory', 'source_module', 'target_model', 'target_model_ref'),
        ('compliance.CriticalActionExecution', 'source_module', 'target_model', 'target_model_ref'),
        ('governance.GovernanceAuditLog', 'module', 'target_model', 'target_model_ref'),
    ]:
        app_label, model_name = model_label.split('.')
        model = apps.get_model(app_label, model_name)
        for obj in model.objects.exclude(**{model_field: ''}).iterator():
            system_model = _system_model(apps, obj.tenant_id, getattr(obj, model_field), getattr(obj, module_field, ''))
            model.objects.filter(pk=obj.pk).update(**{f'{model_fk}_id': getattr(system_model, 'pk', None)})


def _populate_impact_levels(apps):
    for model_label, text_field, fk_field, level_type in [
        ('deviations.QualityEvent', 'severity', 'severity_ref', 'severity'),
        ('deviations.QualityEvent', 'criticality', 'criticality_ref', 'criticality'),
        ('audits.AuditFinding', 'criticality', 'criticality_ref', 'criticality'),
        ('files.ProtectedFile', 'criticality', 'criticality_ref', 'criticality'),
        ('workflow.WorkflowNotification', 'criticality', 'criticality_ref', 'criticality'),
        ('workflow.ApprovalQueue', 'criticality', 'criticality_ref', 'criticality'),
        ('workflow.ApprovalTask', 'criticality', 'criticality_ref', 'criticality'),
        ('governance.GovernanceAuditLog', 'severity', 'severity_ref', 'severity'),
        ('procurement.SupplierQualificationEvent', 'severity', 'severity_ref', 'criticality'),
        ('crm.CustomerComplaint', 'severity', 'severity_ref', 'severity'),
        ('risks.RiskAlert', 'severity', 'severity_ref', 'severity'),
        ('regulatory.RegulatoryAlert', 'severity', 'severity_ref', 'severity'),
        ('pharmacovigilance.PharmacovigilanceCase', 'severity', 'severity_ref', 'severity'),
        ('recalls.MarketComplaint', 'criticality', 'criticality_ref', 'criticality'),
        ('recalls.RecallCampaign', 'criticality', 'criticality_ref', 'criticality'),
    ]:
        app_label, model_name = model_label.split('.')
        model = apps.get_model(app_label, model_name)
        for obj in model.objects.exclude(**{text_field: ''}).iterator():
            impact = _impact(apps, obj.tenant_id, getattr(obj, text_field), level_type)
            model.objects.filter(pk=obj.pk).update(**{f'{fk_field}_id': getattr(impact, 'pk', None)})


def populate_auxiliary_references(apps, schema_editor):
    _populate_area_process_role_department(apps)
    _populate_locations(apps)
    _populate_commercial(apps)
    _populate_system_references(apps)
    _populate_impact_levels(apps)


class Migration(migrations.Migration):
    dependencies = [
        ('auxiliary', '0001_initial'),
        ('ai_agents', '0002_aiagentprofile_source_module_ref_and_more'),
        ('audits', '0002_auditfinding_criticality_ref_auditplan_area_ref'),
        ('changes', '0002_changeassessment_department_ref'),
        ('compliance', '0002_compliancechecklistitem_source_module_ref_and_more'),
        ('crm', '0002_customercomplaint_severity_ref_and_more'),
        ('deviations', '0002_qualityevent_area_ref_qualityevent_criticality_ref_and_more'),
        ('documents', '0002_controlleddocument_area_ref'),
        ('files', '0002_protectedfile_criticality_ref_and_more'),
        ('fiscal', '0002_fiscalcompany_city_ref_fiscalcompany_state_ref_and_more'),
        ('governance', '0002_governanceauditlog_module_ref_and_more'),
        ('maintenance', '0002_equipmentasset_area_ref'),
        ('masters', '0002_businesspartner_city_ref_businesspartner_state_ref'),
        ('pharmacovigilance', '0002_pharmacovigilancecase_country_ref_and_more'),
        ('procurement', '0002_purchaseorder_currency_ref_and_more'),
        ('qa', '0002_criticalactivityrule_area_ref_and_more'),
        ('recalls', '0002_marketcomplaint_criticality_ref_and_more'),
        ('regulatory', '0002_regulatoryalert_severity_ref'),
        ('reports', '0002_dashboardwidget_module_ref_and_more'),
        ('risks', '0002_riskalert_severity_ref_riskrecord_process_ref'),
        ('training', '0002_criticalactivityrule_area_ref_and_more'),
        ('workflow', '0002_approvalqueue_area_ref_approvalqueue_criticality_ref_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_auxiliary_references, migrations.RunPython.noop),
    ]
