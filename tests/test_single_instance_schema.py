import importlib

from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import DeleteModel, RemoveField, RemoveIndex
import pytest


def test_constraint_cleanup_migration_uses_portable_reversible_names():
    migration = importlib.import_module(
        'compliance.migrations.0007_rename_legacy_tenant_not_null_constraint'
    )

    assert len(migration.NEW_CONSTRAINT.encode()) <= 63
    assert migration.OLD_CONSTRAINT in migration.FORWARD_SQL
    assert migration.NEW_CONSTRAINT in migration.FORWARD_SQL
    assert migration.NEW_CONSTRAINT in migration.REVERSE_SQL
    assert migration.OLD_CONSTRAINT in migration.REVERSE_SQL


def test_destructive_cleanup_migrations_keep_real_reverse_operations_and_ordering():
    accounts_invitation = importlib.import_module(
        'accounts.migrations.0008_delete_tenantmembershipinvitation'
    ).Migration
    accounts_membership = importlib.import_module(
        'accounts.migrations.0009_delete_tenantmembership'
    ).Migration
    governance_setting = importlib.import_module(
        'governance.migrations.0006_delete_tenantmodulesetting'
    ).Migration
    tenant_field = importlib.import_module(
        'tenants.migrations.0005_remove_tenant_tenants_ten_module__12574a_idx_and_more'
    ).Migration
    tenant_delete = importlib.import_module('tenants.migrations.0006_delete_tenant').Migration

    assert all(isinstance(item, DeleteModel) for item in accounts_invitation.operations)
    assert all(isinstance(item, DeleteModel) for item in accounts_membership.operations)
    assert all(isinstance(item, DeleteModel) for item in governance_setting.operations)
    assert [type(item) for item in tenant_field.operations] == [RemoveIndex, RemoveField]
    assert ('accounts', '0009_delete_tenantmembership') in tenant_delete.dependencies
    assert ('governance', '0006_delete_tenantmodulesetting') in tenant_delete.dependencies


@pytest.mark.django_db
def test_tenant_model_deletion_waits_for_every_tenant_cleanup_migration():
    cleanup_migrations = {
        ('accounts', '0009_delete_tenantmembership'),
        ('ai_agents', '0004_remove_aiagentprofile_unique_tenant_ai_agent_profile_code_and_more'),
        ('audits', '0004_remove_auditplan_unique_tenant_audit_number_and_more'),
        (
            'auxiliary',
            '0004_remove_businessarea_unique_auxiliary_businessarea_tenant_code_and_more',
        ),
        ('capa', '0002_remove_capaapproval_unique_tenant_capa_approval_role_user_and_more'),
        ('changes', '0003_remove_changeapproval_unique_tenant_change_approval_role_user_and_more'),
        ('compliance', '0007_rename_legacy_tenant_not_null_constraint'),
        ('control_plane', '0004_remove_platformauditevent_tenant_and_more'),
        ('costing', '0002_remove_costcenter_unique_tenant_cost_center_code_and_more'),
        ('crm', '0004_remove_campaign_unique_tenant_campaign_code_and_more'),
        (
            'deviations',
            '0003_remove_deviationapproval_unique_tenant_deviation_approval_role_user_and_more',
        ),
        (
            'documents',
            '0003_remove_controlleddocument_unique_tenant_document_code_version_and_more',
        ),
        ('files', '0004_remove_protectedfile_unique_tenant_protected_file_number_and_more'),
        (
            'finance',
            '0002_remove_chartofaccount_unique_tenant_chart_account_code_and_more',
        ),
        (
            'fiscal',
            '0005_remove_fiscalbookentry_unique_tenant_document_book_entry_and_more',
        ),
        (
            'formulations',
            '0002_remove_manufacturingroute_unique_tenant_route_product_version_and_more',
        ),
        ('governance', '0006_delete_tenantmodulesetting'),
        (
            'integrations',
            '0003_remove_apiclientapplication_unique_tenant_api_client_code_and_more',
        ),
        (
            'inventory',
            '0002_remove_stockbalance_unique_tenant_stock_balance_address_status_and_more',
        ),
        (
            'knowledge',
            '0002_remove_knowledgechunk_unique_tenant_document_chunk_index_and_more',
        ),
        (
            'maintenance',
            '0004_remove_equipmentasset_unique_tenant_equipment_asset_code_and_more',
        ),
        ('masters', '0004_remove_businesspartner_unique_tenant_partner_code_and_more'),
        (
            'pharmacovigilance',
            '0004_remove_pharmacovigilanceaction_unique_tenant_pharmacovigilance_action_number_and_more',
        ),
        (
            'planning',
            '0002_remove_capacityresource_unique_tenant_capacity_resource_code_and_more',
        ),
        (
            'procurement',
            '0004_remove_purchaseorder_unique_tenant_purchase_order_number_and_more',
        ),
        (
            'production',
            '0002_remove_productionorder_unique_tenant_production_order_number_and_more',
        ),
        ('qa', '0003_remove_criticalactivityrule_unique_tenant_critical_activity_code_and_more'),
        (
            'quality',
            '0003_remove_analyticalspecification_unique_tenant_qc_spec_product_lot_version_and_more',
        ),
        (
            'recalls',
            '0004_remove_marketcomplaint_unique_tenant_market_complaint_number_and_more',
        ),
        (
            'regulatory',
            '0004_remove_regulatorycommitment_unique_tenant_regulatory_commitment_number_and_more',
        ),
        (
            'reports',
            '0003_remove_dashboardworkspace_unique_tenant_dashboard_workspace_code_and_more',
        ),
        ('risks', '0003_remove_riskrecord_unique_tenant_risk_number_and_more'),
        ('training', '0004_remove_competency_unique_tenant_competency_code_and_more'),
        (
            'workflow',
            '0003_remove_approvalqueue_unique_tenant_approval_queue_code_and_more',
        ),
    }
    loader = MigrationLoader(connection)
    tenant_delete_ancestors = set(loader.graph.forwards_plan(('tenants', '0006_delete_tenant')))

    assert cleanup_migrations <= tenant_delete_ancestors


@pytest.mark.django_db
def test_operational_models_and_postgresql_schema_have_no_tenant_artifacts():
    models_with_tenant = [
        model._meta.label
        for model in apps.get_models()
        if any(field.name == 'tenant' for field in model._meta.get_fields())
    ]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'tenant_id'
            ORDER BY table_name
            """
        )
        tenant_columns = cursor.fetchall()
        cursor.execute(
            """
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public' AND indexdef ILIKE '%tenant%'
            ORDER BY tablename, indexname
            """
        )
        tenant_indexes = cursor.fetchall()
        cursor.execute(
            """
            SELECT conrelid::regclass::text, conname
            FROM pg_constraint
            WHERE conname ILIKE '%tenant%'
            ORDER BY conrelid::regclass::text, conname
            """
        )
        tenant_constraints = cursor.fetchall()

    assert models_with_tenant == []
    assert tenant_columns == []
    assert tenant_indexes == []
    assert tenant_constraints == []
