from __future__ import annotations

from copy import deepcopy
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data
from auxiliary.management.commands.refresh_official_reference_snapshots import (
    Command as RefreshCommand,
)
from auxiliary.models import City, Country, Currency, StateProvince
from auxiliary.reference_snapshots import OfficialReferenceSnapshot, apply_official_snapshot


pytestmark = pytest.mark.django_db


MINIMAL_PAYLOAD = {
    'countries': [
        {
            'iso_alpha2': 'BR',
            'iso_alpha3': 'BRA',
            'name': 'Brasil',
            'numeric_code': '076',
        }
    ],
    'states': [
        {
            'abbreviation': 'PE',
            'country_iso_alpha2': 'BR',
            'ibge_code': '26',
            'name': 'Pernambuco',
        }
    ],
    'cities': [
        {'ibge_code': '2611606', 'name': 'Recife', 'state_ibge_code': '26'},
    ],
    'currencies': [
        {
            'code': 'BRL',
            'decimal_places': 2,
            'description': 'Moeda ISO 4217 com nome localizado para português do Brasil.',
            'minor_unit_applicable': True,
            'name': 'Real brasileiro',
            'numeric_code': '986',
            'source_entities': ['BRAZIL'],
            'source_name': 'Brazilian Real',
            'symbol': 'R$',
        }
    ],
}


def _snapshot(payload=None):
    return OfficialReferenceSnapshot(
        manifest=Mock(),
        payload=deepcopy(payload if payload is not None else MINIMAL_PAYLOAD),
    )


def test_official_location_codes_are_primary_and_allow_official_name_refresh():
    country = Country.objects.create(
        name='Brasil antes da atualização',
        iso_alpha2='BR',
        iso_alpha3='BRA',
        numeric_code='076',
    )
    state = StateProvince.objects.create(
        name='Pernambuco antes da atualização',
        country=country,
        abbreviation='PE',
        ibge_code='26',
    )
    city = City.objects.create(
        name='Recife antes da atualização',
        state=state,
        ibge_code='2611606',
    )
    original_ids = (country.pk, state.pk, city.pk)

    apply_official_snapshot(_snapshot())

    country.refresh_from_db()
    state.refresh_from_db()
    city.refresh_from_db()
    assert (country.pk, state.pk, city.pk) == original_ids
    assert country.name == 'Brasil'
    assert state.name == 'Pernambuco'
    assert city.name == 'Recife'
    assert Country.objects.count() == 1
    assert StateProvince.objects.count() == 1
    assert City.objects.count() == 1


def test_exact_legacy_location_hierarchy_receives_official_codes_idempotently():
    country = Country.objects.create(name='Brasil')
    state = StateProvince.objects.create(name='Pernambuco', country=country)
    city = City.objects.create(name='Recife', state=state)
    original_ids = (country.pk, state.pk, city.pk)

    apply_official_snapshot(_snapshot())
    apply_official_snapshot(_snapshot())

    country.refresh_from_db()
    state.refresh_from_db()
    city.refresh_from_db()
    assert (country.pk, state.pk, city.pk) == original_ids
    assert (country.iso_alpha2, country.iso_alpha3, country.numeric_code) == (
        'BR',
        'BRA',
        '076',
    )
    assert (state.abbreviation, state.ibge_code) == ('PE', '26')
    assert city.ibge_code == '2611606'
    assert Country.objects.count() == 1
    assert StateProvince.objects.count() == 1
    assert City.objects.count() == 1


def test_official_location_identity_conflict_aborts_without_merging_records():
    official = Country.objects.create(
        name='Brasil cadastrado pelo código',
        iso_alpha2='BR',
        iso_alpha3='BRA',
        numeric_code='076',
    )
    legacy = Country.objects.create(name='Brasil')

    with pytest.raises(CommandError, match='(?i)conflito|diverg'):
        apply_official_snapshot(_snapshot())

    official.refresh_from_db()
    legacy.refresh_from_db()
    assert official.name == 'Brasil cadastrado pelo código'
    assert legacy.name == 'Brasil'
    assert legacy.iso_alpha2 == ''
    assert StateProvince.objects.count() == 0


def test_ambiguous_legacy_location_aborts_without_partial_write():
    country = Country.objects.create(
        name='Brasil',
        iso_alpha2='BR',
        iso_alpha3='BRA',
        numeric_code='076',
    )
    StateProvince.objects.create(name='Pernambuco', country=country)
    StateProvince.objects.create(name='Pernambuco', country=country)

    with pytest.raises(CommandError, match='Mais de um cadastro local'):
        apply_official_snapshot(_snapshot())

    assert StateProvince.objects.filter(country=country, name='Pernambuco').count() == 2
    assert not StateProvince.objects.exclude(abbreviation='').exists()
    assert City.objects.count() == 0


def test_currency_parser_rejects_duplicate_nonblank_numeric_code():
    xml = b"""<ISO_4217 Pblshd="2026-01-01"><CcyTbl>
    <CcyNtry><CtryNm>BRAZIL</CtryNm><CcyNm>Brazilian Real</CcyNm>
      <Ccy>BRL</Ccy><CcyNbr>986</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry>
    <CcyNtry><CtryNm>TEST</CtryNm><CcyNm>Test Currency</CcyNm>
      <Ccy>TST</Ccy><CcyNbr>986</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry></CcyTbl></ISO_4217>"""

    with pytest.raises(CommandError, match='Código numérico.*duplicado|numeric_code'):
        RefreshCommand._parse_currencies(xml)


def test_currency_parser_separates_source_provenance_from_pt_br_description():
    xml = b"""<ISO_4217 Pblshd="2026-01-01"><CcyTbl><CcyNtry>
      <CtryNm>BRAZIL</CtryNm><CcyNm>Brazilian Real</CcyNm>
      <Ccy>BRL</Ccy><CcyNbr>986</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry></CcyTbl></ISO_4217>"""

    [currency] = RefreshCommand._parse_currencies(xml)

    assert currency['description'] == (
        'Moeda ISO 4217 com nome localizado para português do Brasil.'
    )
    assert currency['source_name'] == 'Brazilian Real'
    assert currency['source_entities'] == ['BRAZIL']
    assert 'Brazilian Real' not in currency['description']
    assert 'BRAZIL' not in currency['description']


def test_currency_numeric_code_is_unique_in_database_when_nonblank():
    Currency.objects.create(code='BRL', name='Real brasileiro', numeric_code='986')

    with pytest.raises(IntegrityError), transaction.atomic():
        Currency.objects.create(code='TST', name='Moeda de teste', numeric_code='986')

    Currency.objects.create(code='LOC-A', name='Moeda local A', numeric_code='')
    Currency.objects.create(code='LOC-B', name='Moeda local B', numeric_code='')


def test_currency_second_snapshot_run_validates_without_update_or_timestamp_change(monkeypatch):
    apply_official_snapshot(_snapshot())
    currency = Currency.objects.get(code='BRL')
    original_updated_at = currency.updated_at
    full_clean_calls = 0
    original_full_clean = Currency.full_clean
    writes = []

    def record_full_clean(instance, *args, **kwargs):
        nonlocal full_clean_calls
        full_clean_calls += 1
        return original_full_clean(instance, *args, **kwargs)

    def record_currency_write(execute, sql, params, many, context):
        normalized = sql.lstrip().upper()
        if normalized.startswith('UPDATE') and 'AUXILIARY_CURRENCY' in normalized:
            writes.append(sql)
        return execute(sql, params, many, context)

    monkeypatch.setattr(Currency, 'full_clean', record_full_clean)
    with connection.execute_wrapper(record_currency_write):
        apply_official_snapshot(_snapshot())

    currency.refresh_from_db()
    assert full_clean_calls == 1
    assert writes == []
    assert currency.updated_at == original_updated_at


def test_auxiliary_second_run_validates_without_writes_or_timestamp_change(monkeypatch):
    from auxiliary.models import BusinessArea

    seed_cosmetics_auxiliary_data()
    area = BusinessArea.objects.get(code='BA-COS-PROD')
    original_updated_at = area.updated_at
    full_clean_calls = 0
    original_full_clean = BusinessArea.full_clean
    writes = []

    def record_full_clean(instance, *args, **kwargs):
        nonlocal full_clean_calls
        full_clean_calls += 1
        return original_full_clean(instance, *args, **kwargs)

    def record_write(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            writes.append(sql)
        return execute(sql, params, many, context)

    monkeypatch.setattr(BusinessArea, 'full_clean', record_full_clean)
    with connection.execute_wrapper(record_write):
        seed_cosmetics_auxiliary_data()

    area.refresh_from_db()
    assert full_clean_calls == 14
    assert writes == []
    assert area.updated_at == original_updated_at


def test_offline_combined_command_accepts_and_ignores_legacy_timeout():
    stdout = StringIO()

    with (
        patch(
            'auxiliary.management.commands.load_cosmetics_auxiliary_data.call_command'
        ) as nested_call,
        patch(
            'auxiliary.management.commands.load_cosmetics_auxiliary_data.seed_cosmetics_auxiliary_data',
            return_value={'business_areas': 14},
        ) as seed_auxiliary,
    ):
        call_command(
            'load_cosmetics_auxiliary_data',
            with_official_references=True,
            timeout=120,
            stdout=stdout,
        )

    nested_call.assert_called_once_with('load_official_reference_data')
    seed_auxiliary.assert_called_once_with()
    assert 'Carga auxiliar cosmética concluída' in stdout.getvalue()
