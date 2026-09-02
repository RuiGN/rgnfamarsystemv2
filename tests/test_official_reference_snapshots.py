from __future__ import annotations

import hashlib
import json
from io import StringIO
from unittest.mock import Mock, patch

import pytest
import requests
from babel.numbers import get_currency_name
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from auxiliary.management.commands.refresh_official_reference_snapshots import (
    Command as RefreshCommand,
)
from auxiliary.models import City, Country, Currency, StateProvince
from auxiliary.reference_snapshots import apply_official_snapshot, load_official_snapshot
from reference_data.manifest import CatalogManifest, canonical_json, payload_hash


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
        {'ibge_code': '2609600', 'name': 'Olinda', 'state_ibge_code': '26'},
        {'ibge_code': '2611606', 'name': 'Recife', 'state_ibge_code': '26'},
    ],
    'currencies': [
        {
            'code': 'BRL',
            'decimal_places': 2,
            'description': 'Moeda oficial do Brasil.',
            'minor_unit_applicable': True,
            'name': 'Real brasileiro',
            'numeric_code': '986',
            'symbol': 'R$',
        },
        {
            'code': 'USD',
            'decimal_places': 2,
            'description': 'Dólar dos Estados Unidos.',
            'minor_unit_applicable': True,
            'name': 'Dólar americano',
            'numeric_code': '840',
            'symbol': 'US$',
        },
    ],
}


def _manifest_dict(payload=MINIMAL_PAYLOAD):
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return {
        'expected_counts': {key: len(value) for key, value in payload.items()},
        'identifier': 'official-references-br',
        'namespaces': ['ISO-3166', 'IBGE-LOCALIDADES', 'ISO-4217'],
        'sha256': hashlib.sha256(canonical_payload.encode()).hexdigest(),
        'source_date': '2026-08-31',
        'source_urls': [
            'https://servicodados.ibge.gov.br/api/v1/localidades/paises?orderBy=nome',
            'https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome',
            'https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome',
            'https://www.six-group.com/list-one.xml',
        ],
        'version': '2026.08.31-test',
    }


def write_minimal_snapshot(tmp_path, payload=MINIMAL_PAYLOAD):
    snapshot_path = tmp_path / 'official_references.json'
    manifest_path = tmp_path / 'official_references.manifest.json'
    snapshot_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    manifest_path.write_text(
        json.dumps(_manifest_dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return snapshot_path, manifest_path


def test_catalog_manifest_has_deterministic_canonical_hash():
    manifest = CatalogManifest(
        identifier='official-references-br',
        version='2026.08.31',
        source_date='2026-08-31',
        source_urls=('https://example.test/catalog',),
        namespaces=('ISO-3166',),
        expected_counts={'countries': 1},
        sha256='a' * 64,
    )
    expected_payload = {
        'expected_counts': {'countries': 1},
        'identifier': 'official-references-br',
        'namespaces': ['ISO-3166'],
        'sha256': 'a' * 64,
        'source_date': '2026-08-31',
        'source_urls': ['https://example.test/catalog'],
        'version': '2026.08.31',
    }

    expected = hashlib.sha256(
        json.dumps(
            expected_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode()
    ).hexdigest()

    assert canonical_json({'b': 'ação', 'a': 1}) == '{"a":1,"b":"ação"}'
    assert payload_hash(MINIMAL_PAYLOAD) == _manifest_dict()['sha256']
    assert manifest.canonical_hash() == expected


@pytest.mark.django_db
def test_official_loader_uses_committed_snapshot_without_network(tmp_path, monkeypatch):
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)
    monkeypatch.setattr(requests, 'get', Mock(side_effect=AssertionError('rede proibida')))

    result = load_official_snapshot(snapshot_path, manifest_path)
    counts = apply_official_snapshot(result)

    assert counts == {'countries': 1, 'states': 1, 'cities': 2, 'currencies': 2}
    assert City.objects.get(ibge_code='2611606').name == 'Recife'


def test_snapshot_rejects_manifest_hash_mismatch(tmp_path):
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)
    snapshot_path.write_text('{}\n', encoding='utf-8')

    with pytest.raises(CommandError, match='SHA-256'):
        load_official_snapshot(snapshot_path, manifest_path)


@pytest.mark.parametrize(
    ('payload', 'message'),
    [
        ({**MINIMAL_PAYLOAD, 'unexpected': []}, 'seções ausentes ou inesperadas'),
        ({**MINIMAL_PAYLOAD, 'cities': MINIMAL_PAYLOAD['cities'][:1]}, 'Contagem divergente'),
    ],
)
def test_snapshot_rejects_invalid_sections_and_counts(tmp_path, payload, message):
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path, payload)
    if 'unexpected' not in payload:
        manifest = _manifest_dict(payload)
        manifest['expected_counts'] = _manifest_dict()['expected_counts']
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )

    with pytest.raises(CommandError, match=message):
        load_official_snapshot(snapshot_path, manifest_path)


@pytest.mark.django_db
def test_loader_does_not_adopt_a_location_only_because_official_code_matches(tmp_path):
    local = Country.objects.create(
        name='País local',
        iso_alpha2='BR',
        iso_alpha3='BRA',
        numeric_code='076',
    )
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)

    with pytest.raises(CommandError, match='Código oficial já pertence a outro país'):
        apply_official_snapshot(load_official_snapshot(snapshot_path, manifest_path))

    local.refresh_from_db()
    assert local.name == 'País local'
    assert Country.objects.count() == 1
    assert StateProvince.objects.count() == 0
    assert City.objects.count() == 0
    assert Currency.objects.count() == 0


@pytest.mark.django_db
def test_loader_does_not_adopt_state_or_city_only_because_ibge_code_matches(tmp_path):
    brazil = Country.objects.create(
        name='Brasil',
        iso_alpha2='BR',
        iso_alpha3='BRA',
        numeric_code='076',
    )
    local_state = StateProvince.objects.create(
        name='Estado local',
        country=brazil,
        abbreviation='PE',
        ibge_code='26',
    )
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)

    with pytest.raises(CommandError, match='Código oficial já pertence a outro cadastro de UF'):
        apply_official_snapshot(load_official_snapshot(snapshot_path, manifest_path))

    local_state.refresh_from_db()
    assert local_state.name == 'Estado local'
    assert StateProvince.objects.count() == 1
    assert City.objects.count() == 0

    local_state.name = 'Pernambuco'
    local_state.save(update_fields=['name'])
    City.objects.create(name='Cidade local', state=local_state, ibge_code='2611606')

    with pytest.raises(CommandError, match='Código oficial já pertence a outro município'):
        apply_official_snapshot(load_official_snapshot(snapshot_path, manifest_path))

    assert City.objects.get(ibge_code='2611606').name == 'Cidade local'
    assert City.objects.count() == 1
    assert Currency.objects.count() == 0


@pytest.mark.django_db
def test_load_command_is_offline_and_has_no_download_options(tmp_path, monkeypatch):
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)
    monkeypatch.setattr(
        'auxiliary.reference_snapshots.DEFAULT_SNAPSHOT_PATH',
        snapshot_path,
    )
    monkeypatch.setattr(
        'auxiliary.reference_snapshots.DEFAULT_MANIFEST_PATH',
        manifest_path,
    )
    monkeypatch.setattr(requests, 'get', Mock(side_effect=AssertionError('rede proibida')))
    stdout = StringIO()

    call_command('load_official_reference_data', stdout=stdout)

    output = stdout.getvalue()
    assert 'Carga oficial versionada concluída' in output
    assert 'countries=1, states=1, cities=2, currencies=2' in output
    assert 'versão=2026.08.31-test' in output
    with pytest.raises(TypeError, match='Unknown option'):
        call_command('load_official_reference_data', timeout=1)


def test_refresh_command_writes_deterministic_snapshot_and_manifest(tmp_path):
    stdout = StringIO()

    with (
        patch(
            'auxiliary.management.commands.refresh_official_reference_snapshots.Command.fetch_and_parse',
            return_value=MINIMAL_PAYLOAD,
        ) as fetch,
        patch(
            'auxiliary.management.commands.refresh_official_reference_snapshots.Command._validate_cardinality'
        ),
    ):
        call_command(
            'refresh_official_reference_snapshots',
            version='2026.08.31-test',
            source_date='2026-08-31',
            output_dir=tmp_path,
            timeout=45,
            stdout=stdout,
        )

    fetch.assert_called_once_with(timeout=45)
    snapshot_path = tmp_path / 'official_references.json'
    manifest_path = tmp_path / 'official_references.manifest.json'
    assert snapshot_path.read_bytes().endswith(b'\n')
    assert manifest_path.read_bytes().endswith(b'\n')
    assert json.loads(snapshot_path.read_text(encoding='utf-8')) == MINIMAL_PAYLOAD
    loaded = load_official_snapshot(snapshot_path, manifest_path)
    assert loaded.manifest.version == '2026.08.31-test'
    assert loaded.manifest.sha256 == payload_hash(MINIMAL_PAYLOAD)
    assert 'Snapshot oficial atualizado' in stdout.getvalue()


def test_refresh_fetch_and_parse_normalizes_the_four_official_sources():
    countries = [
        {
            'id': {'M49': 76, 'ISO-ALPHA-2': 'BR', 'ISO-ALPHA-3': 'BRA'},
            'nome': 'Brasil',
        }
    ]
    states = [{'id': 26, 'sigla': 'PE', 'nome': 'Pernambuco'}]
    cities = [
        {
            'id': 2611606,
            'nome': 'Recife',
            'regiao-imediata': {'regiao-intermediaria': {'UF': {'id': 26, 'sigla': 'PE'}}},
        }
    ]
    currencies = b"""<?xml version="1.0" encoding="UTF-8"?>
    <ISO_4217 Pblshd="2026-01-01"><CcyTbl><CcyNtry>
      <CtryNm>BRAZIL</CtryNm><CcyNm>Brazilian Real</CcyNm>
      <Ccy>BRL</Ccy><CcyNbr>986</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry></CcyTbl></ISO_4217>"""
    command = RefreshCommand()

    with (
        patch.object(command, '_download_json', side_effect=[countries, states, cities]),
        patch.object(command, '_download_bytes', return_value=currencies),
    ):
        payload = command.fetch_and_parse(timeout=45)

    assert payload == {
        'countries': [
            {
                'name': 'Brasil',
                'iso_alpha2': 'BR',
                'iso_alpha3': 'BRA',
                'numeric_code': '076',
            }
        ],
        'states': [
            {
                'name': 'Pernambuco',
                'abbreviation': 'PE',
                'ibge_code': '26',
                'country_iso_alpha2': 'BR',
            }
        ],
        'cities': [{'name': 'Recife', 'state_ibge_code': '26', 'ibge_code': '2611606'}],
        'currencies': [
            {
                'code': 'BRL',
                'name': 'Real brasileiro',
                'numeric_code': '986',
                'decimal_places': 2,
                'minor_unit_applicable': True,
                'symbol': 'R$',
                'description': (
                    'Nome oficial SIX: Brazilian Real. Entidades usuárias: BRAZIL. '
                    'Fonte: ISO 4217/SIX (lista vigente em 2026-01-01).'
                ),
            }
        ],
    }


def test_currency_parser_uses_explicit_pt_br_name_when_cldr_has_no_translation():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <ISO_4217 Pblshd="2026-01-01"><CcyTbl><CcyNtry>
      <CtryNm>URUGUAY</CtryNm><CcyNm>Unidad Previsional</CcyNm>
      <Ccy>UYW</Ccy><CcyNbr>927</CcyNbr><CcyMnrUnts>4</CcyMnrUnts>
    </CcyNtry></CcyTbl></ISO_4217>"""

    with patch(
        'auxiliary.management.commands.refresh_official_reference_snapshots.get_currency_name',
        return_value='UYW',
    ):
        currencies = RefreshCommand._parse_currencies(xml)

    assert currencies[0]['name'] == 'Unidade previdenciária'
    assert 'Nome oficial SIX: Unidad Previsional.' in currencies[0]['description']


PT_BR_CURRENCY_NAMES = {
    'UYW': 'Unidade previdenciária',
    'VED': 'Bolívar soberano',
    'XAD': 'Dinar contábil árabe',
    'XCG': 'Guilda caribenha',
    'XSU': 'Sucre',
    'XUA': 'Unidade de conta do Banco Asiático de Desenvolvimento',
    'ZWG': 'Ouro do Zimbábue',
}
SIX_CURRENCY_NAMES = {
    'UYW': 'Unidad Previsional',
    'VED': 'Bolívar Soberano',
    'XAD': 'Arab Accounting Dinar',
    'XCG': 'Caribbean Guilder',
    'XSU': 'Sucre',
    'XUA': 'ADB Unit of Account',
    'ZWG': 'Zimbabwe Gold',
}


def test_currency_parser_uses_versioned_pt_br_names_and_preserves_six_provenance():
    rows = ''.join(
        '<CcyNtry>'
        f'<CtryNm>ENTIDADE {code}</CtryNm><CcyNm>{six_name}</CcyNm>'
        f'<Ccy>{code}</Ccy><CcyNbr>{900 + index}</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>'
        '</CcyNtry>'
        for index, (code, six_name) in enumerate(SIX_CURRENCY_NAMES.items())
    )
    xml = f'<ISO_4217 Pblshd="2026-01-01"><CcyTbl>{rows}</CcyTbl></ISO_4217>'.encode()

    with patch(
        'auxiliary.management.commands.refresh_official_reference_snapshots.get_currency_name',
        side_effect=lambda code, locale: code,
    ):
        currencies = RefreshCommand._parse_currencies(xml)

    assert {row['code']: row['name'] for row in currencies} == PT_BR_CURRENCY_NAMES
    for row in currencies:
        assert f'Nome oficial SIX: {SIX_CURRENCY_NAMES[row["code"]]}.' in row['description']


def test_every_committed_currency_name_is_pt_br_and_has_stable_explicit_overrides():
    snapshot = load_official_snapshot()
    currencies = {row['code']: row for row in snapshot.payload['currencies']}

    assert {code: currencies[code]['name'] for code in PT_BR_CURRENCY_NAMES} == (
        PT_BR_CURRENCY_NAMES
    )
    for code, row in currencies.items():
        expected_name = (
            PT_BR_CURRENCY_NAMES.get(code)
            or str(get_currency_name(code, locale='pt_BR') or '').strip()
        )
        assert expected_name and expected_name != code
        assert row['name'] == expected_name
    for code, official_name in SIX_CURRENCY_NAMES.items():
        assert f'Nome oficial SIX: {official_name}.' in currencies[code]['description']


def test_currency_parser_represents_non_applicable_minor_units_explicitly():
    xml = b"""<ISO_4217 Pblshd="2026-01-01"><CcyTbl>
    <CcyNtry><CtryNm>GOLD</CtryNm><CcyNm>Gold</CcyNm>
      <Ccy>XAU</Ccy><CcyNbr>959</CcyNbr><CcyMnrUnts>N.A.</CcyMnrUnts>
    </CcyNtry>
    <CcyNtry><CtryNm>BRAZIL</CtryNm><CcyNm>Brazilian Real</CcyNm>
      <Ccy>BRL</Ccy><CcyNbr>986</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry></CcyTbl></ISO_4217>"""

    currencies = {row['code']: row for row in RefreshCommand._parse_currencies(xml)}

    assert currencies['XAU']['minor_unit_applicable'] is False
    assert currencies['XAU']['decimal_places'] == 0
    assert currencies['BRL']['minor_unit_applicable'] is True
    assert currencies['BRL']['decimal_places'] == 2


@pytest.mark.parametrize('minor_units', ['', 'desconhecido'])
def test_currency_parser_rejects_unknown_minor_unit_value(minor_units):
    xml = f"""<ISO_4217 Pblshd="2026-01-01"><CcyTbl><CcyNtry>
      <CtryNm>TEST</CtryNm><CcyNm>Test Currency</CcyNm>
      <Ccy>TST</Ccy><CcyNbr>999</CcyNbr><CcyMnrUnts>{minor_units}</CcyMnrUnts>
    </CcyNtry></CcyTbl></ISO_4217>""".encode()

    with pytest.raises(CommandError, match='Valor de unidade menor inválido'):
        RefreshCommand._parse_currencies(xml)


def test_currency_model_and_admin_expose_minor_unit_applicability():
    field = Currency._meta.get_field('minor_unit_applicable')

    assert field.default is True
    assert field.verbose_name == 'unidade monetária menor aplicável'
    assert 'minor_unit_applicable' in admin.site._registry[Currency].list_display


@pytest.mark.django_db
def test_currency_full_clean_rejects_decimal_places_for_non_applicable_minor_unit():
    currency = Currency(
        code='XAU',
        name='Ouro',
        numeric_code='959',
        decimal_places=2,
        minor_unit_applicable=False,
    )

    with pytest.raises(ValidationError, match='devem ser zero'):
        currency.full_clean()


@pytest.mark.django_db
def test_currency_numeric_code_collision_on_create_rolls_back_snapshot(tmp_path):
    local = Currency.objects.create(code='LOCAL', name='Moeda local', numeric_code='986')
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)

    with pytest.raises(CommandError, match='Código numérico oficial já pertence a outra moeda'):
        apply_official_snapshot(load_official_snapshot(snapshot_path, manifest_path))

    local.refresh_from_db()
    assert local.name == 'Moeda local'
    assert Currency.objects.count() == 1
    assert Country.objects.count() == 0
    assert StateProvince.objects.count() == 0
    assert City.objects.count() == 0


@pytest.mark.django_db
def test_currency_numeric_code_collision_on_update_rolls_back_before_mutation(tmp_path):
    brl = Currency.objects.create(
        code='BRL',
        name='Real local preservado',
        description='Descrição local preservada',
        numeric_code='999',
        symbol='RL',
        decimal_places=0,
        minor_unit_applicable=False,
    )
    Currency.objects.create(code='LOCAL', name='Moeda local', numeric_code='986')
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)

    with pytest.raises(CommandError, match='Código numérico oficial já pertence a outra moeda'):
        apply_official_snapshot(load_official_snapshot(snapshot_path, manifest_path))

    brl.refresh_from_db()
    assert brl.name == 'Real local preservado'
    assert brl.description == 'Descrição local preservada'
    assert brl.numeric_code == '999'
    assert brl.symbol == 'RL'
    assert brl.decimal_places == 0
    assert brl.minor_unit_applicable is False
    assert Currency.objects.count() == 2
    assert Country.objects.count() == 0


@pytest.mark.parametrize('source_date', ['20260831', '2026-W35-1'])
def test_refresh_command_rejects_non_calendar_source_date_before_network(tmp_path, source_date):
    with (
        patch(
            'auxiliary.management.commands.refresh_official_reference_snapshots.Command.fetch_and_parse'
        ) as fetch,
        pytest.raises(CommandError, match='formato AAAA-MM-DD'),
    ):
        call_command(
            'refresh_official_reference_snapshots',
            version='2026.08.31-test',
            source_date=source_date,
            output_dir=tmp_path,
        )
    fetch.assert_not_called()


@pytest.mark.parametrize('timeout', [0, 301])
def test_refresh_command_rejects_invalid_timeout_before_network(tmp_path, timeout):
    with (
        patch(
            'auxiliary.management.commands.refresh_official_reference_snapshots.Command.fetch_and_parse'
        ) as fetch,
        pytest.raises(CommandError, match='entre 1 e 300'),
    ):
        call_command(
            'refresh_official_reference_snapshots',
            version='2026.08.31-test',
            source_date='2026-08-31',
            output_dir=tmp_path,
            timeout=timeout,
        )
    fetch.assert_not_called()


@pytest.mark.django_db
def test_committed_official_snapshot_has_required_cardinalities_and_valid_hash(monkeypatch):
    monkeypatch.setattr(requests, 'get', Mock(side_effect=AssertionError('rede proibida')))
    snapshot = load_official_snapshot()

    assert len(snapshot.payload['countries']) >= 190
    assert len(snapshot.payload['states']) == 27
    assert len(snapshot.payload['cities']) >= 5500
    assert len(snapshot.payload['currencies']) >= 150
    assert snapshot.manifest.validate_payload(snapshot.payload) is None
    assert set(snapshot.payload) == {'countries', 'states', 'cities', 'currencies'}
    assert {frozenset(row) for row in snapshot.payload['currencies']} == {
        frozenset(
            {
                'code',
                'name',
                'numeric_code',
                'decimal_places',
                'minor_unit_applicable',
                'symbol',
                'description',
            }
        )
    }
    assert apply_official_snapshot(snapshot) == {
        'countries': 193,
        'states': 27,
        'cities': 5571,
        'currencies': 178,
    }
    assert City.objects.get(ibge_code='2611606').name == 'Recife'
    assert Country.objects.count() == 193
    assert StateProvince.objects.count() == 27
    assert City.objects.count() == 5571
    assert Currency.objects.count() == 178
    assert Currency.objects.get(code='BRL').minor_unit_applicable is True
    assert Currency.objects.get(code='XAU').minor_unit_applicable is False
