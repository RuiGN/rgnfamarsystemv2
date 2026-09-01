from django.apps import apps
from django.db import connection
import pytest


requires_postgresql = pytest.mark.skipif(
    connection.vendor != 'postgresql',
    reason='Consulta catálogos information_schema e pg_* do PostgreSQL.',
)


@requires_postgresql
@pytest.mark.django_db
def test_operational_models_and_postgresql_schema_have_no_legacy_scope_artifacts():
    legacy_marker = 'ten' + 'ant'
    models_with_legacy_scope = [
        model._meta.label
        for model in apps.get_models()
        if any(field.name == legacy_marker for field in model._meta.get_fields())
    ]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = %s
            ORDER BY table_name
            """,
            [f'{legacy_marker}_id'],
        )
        legacy_columns = cursor.fetchall()
        cursor.execute(
            """
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public' AND indexdef ILIKE %s
            ORDER BY tablename, indexname
            """,
            [f'%{legacy_marker}%'],
        )
        legacy_indexes = cursor.fetchall()
        cursor.execute(
            """
            SELECT conrelid::regclass::text, conname
            FROM pg_constraint
            WHERE conname ILIKE %s
            ORDER BY conrelid::regclass::text, conname
            """,
            [f'%{legacy_marker}%'],
        )
        legacy_constraints = cursor.fetchall()

    assert models_with_legacy_scope == []
    assert legacy_columns == []
    assert legacy_indexes == []
    assert legacy_constraints == []
