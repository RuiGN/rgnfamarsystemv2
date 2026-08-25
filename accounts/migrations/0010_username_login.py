import re

from django.db import migrations, models
from django.db.models.functions import Lower


MAX_USERNAME_LENGTH = 150


def _normalize_name(value):
    return ' '.join(str(value or '').split())


def _name_from_email(email):
    prefix = str(email or '').partition('@')[0]
    words = re.sub(r'[._-]+', ' ', prefix)
    return _normalize_name(words).title()


def _deduplicated_name(base_name, used_names):
    base_name = _normalize_name(base_name)[:MAX_USERNAME_LENGTH] or 'Usuário'
    candidate = base_name
    suffix = 2
    while candidate.casefold() in used_names:
        suffix_text = f' {suffix}'
        candidate = f'{base_name[: MAX_USERNAME_LENGTH - len(suffix_text)]}{suffix_text}'
        suffix += 1
    used_names.add(candidate.casefold())
    return candidate


def populate_usernames(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    used_names = set()

    for user in User.objects.order_by('pk').iterator():
        full_name = _normalize_name(f'{user.first_name} {user.last_name}')
        base_name = _normalize_name(user.username) or full_name or _name_from_email(user.email)
        user.username = _deduplicated_name(base_name, used_names)
        user.save(update_fields=['username'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_delete_tenantmembership'),
    ]
    operations = [
        migrations.RunPython(populate_usernames, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='user',
            options={
                'ordering': ['username'],
                'verbose_name': 'usuário',
                'verbose_name_plural': 'usuários',
            },
        ),
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=150, unique=True, verbose_name='nome do usuário'),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(
                Lower('username'),
                name='accounts_user_username_ci_unique',
            ),
        ),
    ]
