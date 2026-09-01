from django.db import migrations, models
import django.db.models.deletion


KIND_MAP = {
    'therapeutic_class': 'product_line',
    'pharmaceutical_form': 'cosmetic_form',
}


def migrate_category_kinds(apps, schema_editor):
    category = apps.get_model('masters', 'MasterCategory')
    for old_value, new_value in KIND_MAP.items():
        category.objects.filter(kind=old_value).update(kind=new_value)


def restore_category_kinds(apps, schema_editor):
    category = apps.get_model('masters', 'MasterCategory')
    for old_value, new_value in KIND_MAP.items():
        category.objects.filter(kind=new_value).update(kind=old_value)


class Migration(migrations.Migration):
    dependencies = [('masters', '0001_initial')]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='therapeutic_class',
            new_name='product_line',
        ),
        migrations.RenameField(
            model_name='product',
            old_name='pharmaceutical_form',
            new_name='cosmetic_form',
        ),
        migrations.RunPython(migrate_category_kinds, restore_category_kinds),
        migrations.AlterField(
            model_name='mastercategory',
            name='kind',
            field=models.CharField(
                choices=[
                    ('family', 'Família'),
                    ('group', 'Grupo'),
                    ('category', 'Categoria'),
                    ('product_line', 'Linha de produto'),
                    ('cosmetic_form', 'Forma cosmética'),
                    ('presentation', 'Apresentação'),
                    ('concentration', 'Concentração'),
                    ('application_area', 'Área de aplicação'),
                ],
                max_length=32,
                verbose_name='tipo',
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='product_line',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='product_line_products',
                to='masters.mastercategory',
                verbose_name='linha de produto',
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='cosmetic_form',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='form_products',
                to='masters.mastercategory',
                verbose_name='forma cosmética',
            ),
        ),
    ]
