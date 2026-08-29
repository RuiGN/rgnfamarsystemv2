from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection

from base.sequences import allocate_identifier_number


@pytest.mark.django_db(transaction=True)
def test_postgresql_allocates_distinct_numbers_concurrently():
    if connection.vendor != 'postgresql':
        pytest.skip('Teste concorrente executado somente no PostgreSQL.')

    barrier = Barrier(2)

    def allocate() -> int:
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return allocate_identifier_number(
                'tests.concurrent:code:global',
                initial_value=lambda: 0,
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        numbers = list(executor.map(lambda _index: allocate(), range(2)))

    assert sorted(numbers) == [1, 2]
