import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.urls import Resolver404, resolve

from base.ui.registry import MODULES


def test_technical_responsible_module_is_not_exposed():
    assert 'technicalresponsible' not in apps.all_models['governance']

    with pytest.raises(Resolver404):
        resolve('/api/governance/technical-responsibles/')

    resource_labels = {resource.label for module in MODULES for resource in module.resources}
    assert 'Responsáveis técnicos' not in resource_labels


@pytest.mark.django_db
def test_technical_responsible_schema_and_metadata_are_deleted():
    tables = set(connection.introspection.table_names())

    assert 'governance_technicalresponsible' not in tables
    assert not ContentType.objects.filter(
        app_label='governance', model='technicalresponsible'
    ).exists()
    assert not Permission.objects.filter(
        content_type__app_label='governance',
        content_type__model='technicalresponsible',
    ).exists()
