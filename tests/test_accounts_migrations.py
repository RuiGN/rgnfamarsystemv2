import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.fixture
def restore_latest_migrations():
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_username_login_migration_populates_unique_deterministic_names(
    restore_latest_migrations,
):
    old_target = ('accounts', '0009_delete_tenantmembership')
    new_target = ('accounts', '0010_username_login')
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps
    OldUser = old_apps.get_model('accounts', 'User')

    first = OldUser.objects.create(
        email='joao@example.com',
        first_name='João',
        last_name='Silva',
    )
    second = OldUser.objects.create(
        email='outro@example.com',
        first_name='João',
        last_name='Silva',
    )
    third = OldUser.objects.create(email='maria.souza@example.com')
    fourth = OldUser.objects.create(
        username='  Existing   User  ',
        email='existing@example.com',
    )
    fifth = OldUser.objects.create(
        username='existing user',
        email='existing-duplicate@example.com',
    )

    executor.loader.build_graph()
    executor.migrate([new_target])
    new_apps = executor.loader.project_state([new_target]).apps
    NewUser = new_apps.get_model('accounts', 'User')

    assert NewUser.objects.get(pk=first.pk).username == 'João Silva'
    assert NewUser.objects.get(pk=second.pk).username == 'João Silva 2'
    assert NewUser.objects.get(pk=third.pk).username == 'Maria Souza'
    assert NewUser.objects.get(pk=fourth.pk).username == 'Existing User'
    assert NewUser.objects.get(pk=fifth.pk).username == 'existing user 2'
