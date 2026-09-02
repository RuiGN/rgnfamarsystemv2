from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase

from auxiliary.models import City, Country, Currency, StateProvince


COUNTRIES = [
    {
        'id': {'M49': 76, 'ISO-ALPHA-2': 'BR', 'ISO-ALPHA-3': 'BRA'},
        'nome': 'Brasil',
    }
]

STATES = [
    {
        'id': 26,
        'sigla': 'PE',
        'nome': 'Pernambuco',
        'regiao': {'id': 2, 'sigla': 'NE', 'nome': 'Nordeste'},
    }
]

CITIES = [
    {
        'id': 2611606,
        'nome': 'Recife',
        'regiao-imediata': {'regiao-intermediaria': {'UF': {'id': 26, 'sigla': 'PE'}}},
    },
    {
        'id': 2609600,
        'nome': 'Olinda',
        'microrregiao': {'mesorregiao': {'UF': {'id': 26, 'sigla': 'PE'}}},
    },
]

CURRENCIES_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ISO_4217 Pblshd="2026-01-01">
  <CcyTbl>
    <CcyNtry>
      <CtryNm>BRAZIL</CtryNm><CcyNm>Brazilian Real</CcyNm>
      <Ccy>BRL</Ccy><CcyNbr>986</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry>
    <CcyNtry>
      <CtryNm>UNITED STATES OF AMERICA</CtryNm><CcyNm>US Dollar</CcyNm>
      <Ccy>USD</Ccy><CcyNbr>840</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry>
    <CcyNtry>
      <CtryNm>PUERTO RICO</CtryNm><CcyNm>US Dollar</CcyNm>
      <Ccy>USD</Ccy><CcyNbr>840</CcyNbr><CcyMnrUnts>2</CcyMnrUnts>
    </CcyNtry>
  </CcyTbl>
</ISO_4217>
"""


class OfficialReferenceDataCommandTests(TestCase):
    def run_command(self, *, cities=CITIES):
        stdout = StringIO()
        with (
            patch(
                'auxiliary.management.commands.load_official_reference_data.Command._download_json',
                side_effect=[COUNTRIES, STATES, cities],
            ),
            patch(
                'auxiliary.management.commands.load_official_reference_data.Command._download_bytes',
                return_value=CURRENCIES_XML,
            ),
        ):
            call_command(
                'load_official_reference_data',
                allow_partial=True,
                stdout=stdout,
            )
        return stdout.getvalue()

    def test_loads_official_catalogs_and_is_idempotent(self):
        output = self.run_command()

        brazil = Country.objects.get(name='Brasil')
        pernambuco = StateProvince.objects.get(name='Pernambuco')
        recife = City.objects.get(name='Recife')
        brl = Currency.objects.get(code='BRL')

        assert brazil.name == 'Brasil'
        assert brazil.iso_alpha2 == 'BR'
        assert brazil.iso_alpha3 == 'BRA'
        assert brazil.numeric_code == '076'
        assert pernambuco.abbreviation == 'PE'
        assert pernambuco.ibge_code == '26'
        assert recife.ibge_code == '2611606'

        assert recife.state == pernambuco
        assert brl.name == 'Real brasileiro'
        assert brl.numeric_code == '986'
        assert brl.symbol == 'R$'
        assert Currency.objects.get(code='USD').name == 'Dólar americano'
        assert Currency.objects.get(code='USD').description == (
            'Entidades usuárias: PUERTO RICO; UNITED STATES OF AMERICA. '
            'Fonte: ISO 4217/SIX (lista vigente em 2026-01-01).'
        )
        assert 'países=1, UFs=1, municípios=2, moedas=2' in output

        self.run_command()

        assert Country.objects.count() == 1
        assert StateProvince.objects.count() == 1
        assert City.objects.count() == 2
        assert Currency.objects.count() == 2

    def test_reuses_existing_normalized_location_records(self):
        brazil = Country.objects.create(name='Brasil')
        pernambuco = StateProvince.objects.create(name='Pernambuco')
        existing_city = City.objects.create(name='Recife', state=pernambuco)

        self.run_command()

        existing_city.refresh_from_db()
        pernambuco.refresh_from_db()

        assert City.objects.get(name='Recife').pk == existing_city.pk
        assert City.objects.filter(name='Recife').count() == 1
        assert Country.objects.get(pk=brazil.pk).name == 'Brasil'
        assert StateProvince.objects.get(pk=pernambuco.pk).name == 'Pernambuco'
        assert pernambuco.country == brazil

    def test_rejects_city_with_unknown_state_without_partial_writes(self):
        invalid_cities = [
            {
                'id': 9999999,
                'nome': 'Município inválido',
                'regiao-imediata': {'regiao-intermediaria': {'UF': {'id': 99, 'sigla': 'XX'}}},
            }
        ]

        with pytest.raises(CommandError, match='UF XX não encontrada'):
            self.run_command(cities=invalid_cities)

        assert Country.objects.count() == 0
        assert StateProvince.objects.count() == 0
        assert City.objects.count() == 0
        assert Currency.objects.count() == 0


@pytest.mark.django_db
def test_official_location_codes_are_unique_when_present():
    Country.objects.create(
        name='Brasil', iso_alpha2='BR', iso_alpha3='BRA', numeric_code='076'
    )

    with pytest.raises(IntegrityError):
        Country.objects.create(name='Brasil duplicado', iso_alpha2='BR')
