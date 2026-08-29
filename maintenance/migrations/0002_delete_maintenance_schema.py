from django.db import migrations


def delete_maintenance_metadata(apps, schema_editor):
    alias = schema_editor.connection.alias
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    content_types = ContentType.objects.using(alias).filter(app_label='maintenance')
    Permission.objects.using(alias).filter(content_type__in=content_types).delete()
    content_types.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('maintenance', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('changes', '0003_remove_changecontrol_equipment_reference_and_more'),
        ('compliance', '0002_alter_compliancechecklistitem_source_module_and_more'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('deviations', '0003_remove_qualityevent_equipment_reference'),
        ('formulations', '0002_remove_routestep_equipment_code'),
        ('governance', '0002_alter_governanceauditlog_module_and_more'),
        ('integrations', '0003_remove_equipment_provider'),
        ('planning', '0002_remove_equipment_capacity_resource'),
        ('procurement', '0002_remove_maintenance_requisition_source'),
        ('production', '0003_remove_productionlaborentry_equipment_code_and_more'),
        ('qa', '0002_remove_qualityblock_equipment_reference_and_more'),
        ('quality', '0002_remove_qualityanalysis_equipment_code'),
        ('risks', '0002_remove_equipment_risk_links'),
        ('training', '0003_remove_criticalactivityrule_training_cr_equipme_c51040_idx_and_more'),
    ]

    operations = [
        migrations.DeleteModel(name='MaintenanceMetricReport'),
        migrations.DeleteModel(name='EquipmentUsageLog'),
        migrations.DeleteModel(name='EquipmentDowntime'),
        migrations.DeleteModel(name='MaintenanceOrder'),
        migrations.DeleteModel(name='MaintenancePlan'),
        migrations.DeleteModel(name='EquipmentAsset'),
        migrations.RunPython(delete_maintenance_metadata),
    ]
