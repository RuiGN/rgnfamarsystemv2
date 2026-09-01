import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection

from base.ui.registry import MODULES


def test_backup_run_model_is_not_exposed():
    assert 'backuprun' not in apps.all_models['auxiliary']

    resource_labels = {resource.label for module in MODULES for resource in module.resources}
    assert 'Execuções de backup' not in resource_labels


@pytest.mark.django_db
def test_backup_run_schema_and_metadata_are_deleted():
    tables = set(connection.introspection.table_names())

    assert 'auxiliary_backuprun' not in tables
    assert not ContentType.objects.filter(app_label='auxiliary', model='backuprun').exists()
    assert not Permission.objects.filter(
        content_type__app_label='auxiliary',
        content_type__model='backuprun',
    ).exists()
