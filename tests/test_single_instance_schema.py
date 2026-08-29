from django.apps import apps
from django.db import connection
import pytest


requires_postgresql = pytest.mark.skipif(
    connection.vendor != 'postgresql',
    reason='Consulta catálogos information_schema e pg_* do PostgreSQL.',
)


@requires_postgresql
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
