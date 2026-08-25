from django.db import migrations, models
from django.db.models import F


def backfill_approved_at_from_created_at(apps, schema_editor):
    """Use immutable creation chronology; updated_at may reflect unrelated edits."""
    StandardCost = apps.get_model('costing', 'StandardCost')
    database_alias = schema_editor.connection.alias
    StandardCost.objects.using(database_alias).filter(
        status='approved',
        approved_at__isnull=True,
    ).update(approved_at=F('created_at'))


class Migration(migrations.Migration):
    dependencies = [
        ('costing', '0002_remove_costcenter_unique_tenant_cost_center_code_and_more'),
    ]

    operations = [
        migrations.RunPython(
            backfill_approved_at_from_created_at,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='standardcost',
            constraint=models.CheckConstraint(
                condition=~models.Q(status='approved')
                | models.Q(approved_at__isnull=False),
                name='standard_cost_approved_at_required',
            ),
        ),
    ]
