import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.urls import Resolver404, resolve

from base.ui.registry import get_modules
from changes.models import ChangeControl
from deviations.models import QualityEvent
from formulations.models import RouteStep
from production.models import ProductionLaborEntry, ProductionOperationExecution, ProductionOrder
from qa.models import QualityBlock
from quality.models import QualityAnalysis
from training.models import CriticalActivityRule, TrainingRequirement


def test_active_models_no_longer_expose_equipment_fields():
    models = (
        RouteStep,
        ProductionOrder,
        ProductionOperationExecution,
        ProductionLaborEntry,
        QualityAnalysis,
        QualityEvent,
        ChangeControl,
        QualityBlock,
        TrainingRequirement,
        CriticalActivityRule,
    )

    for model in models:
        field_names = {field.name for field in model._meta.fields}
        assert 'equipment_code' not in field_names, model._meta.label
        assert 'equipment_reference' not in field_names, model._meta.label
        assert 'equipment' not in field_names, model._meta.label


def test_phase_a_maintenance_app_is_an_empty_tombstone():
    assert list(apps.get_app_config('maintenance').get_models()) == []


@pytest.mark.django_db
def test_phase_a_maintenance_schema_and_metadata_are_deleted():
    tables = set(connection.introspection.table_names())
    assert not {name for name in tables if name.startswith('maintenance_')}
    assert not ContentType.objects.filter(app_label='maintenance').exists()
    assert not Permission.objects.filter(content_type__app_label='maintenance').exists()


def test_ui_registry_does_not_expose_equipment_or_maintenance():
    modules = get_modules()
    assert 'maintenance' not in {module.slug for module in modules}

    for module in modules:
        for resource in module.resources:
            searchable = ' '.join(resource.search_fields)
            displayed = ' '.join(resource.list_display)
            form_fields = ' '.join(resource.form_fields or ())
            assert 'equipment' not in searchable
            assert 'equipment' not in displayed
            assert 'equipment' not in form_fields
            assert 'equipamento' not in resource.label.lower()

            for inline in resource.inlines:
                inline_fields = ' '.join(inline.fields)
                assert 'equipment' not in inline_fields
                assert 'equipamento' not in inline.title.lower()


@pytest.mark.parametrize(
    'path',
    (
        '/api/maintenance/',
        '/api/v1/maintenance/',
        '/app/maintenance/',
    ),
)
def test_maintenance_routes_are_removed_from_public_url_configuration(path):
    with pytest.raises(Resolver404):
        resolve(path)
