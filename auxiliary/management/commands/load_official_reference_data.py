from __future__ import annotations

import logging
from collections import defaultdict

import requests
from babel.numbers import get_currency_name
from defusedxml import ElementTree
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from auxiliary.models import City, Country, Currency, StateProvince


LOGGER = logging.getLogger(__name__)

IBGE_COUNTRIES_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/paises?orderBy=nome'
IBGE_STATES_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome'
IBGE_CITIES_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome'
ISO_CURRENCIES_URL = (
    'https://www.six-group.com/dam/download/financial-information/'
    'data-center/iso-currrency/lists/list-one.xml'
)

EXPECTED_MINIMUMS = {
    'countries': 190,
    'states': 27,
    'cities': 5500,
    'currencies': 150,
}

CURRENCY_SYMBOLS = {
    'ARS': 'AR$',
    'AUD': 'A$',
    'BRL': 'R$',
    'CAD': 'C$',
    'CHF': 'CHF',
    'CLP': 'CL$',
    'CNY': '¥',
    'COP': 'CO$',
    'EUR': '€',
    'GBP': '£',
    'INR': '₹',
    'JPY': '¥',
    'KRW': '₩',
    'MXN': 'MX$',
    'PEN': 'S/',
    'RUB': '₽',
    'USD': 'US$',
}


class Command(BaseCommand):
    help = (
        'Carrega países, UFs, municípios e moedas a partir das fontes oficiais IBGE e ISO 4217/SIX.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=60,
            help='Tempo limite, em segundos, para cada requisição HTTPS.',
        )
        parser.add_argument(
            '--allow-partial',
            action='store_true',
            help='Aceita conjuntos reduzidos. Destinado somente a testes e cargas controladas.',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        if timeout < 1 or timeout > 300:
            raise CommandError('--timeout deve estar entre 1 e 300 segundos.')

        self.stdout.write('Obtendo referências oficiais do IBGE e da ISO 4217/SIX...')
        countries_payload = self._download_json(IBGE_COUNTRIES_URL, timeout)
        states_payload = self._download_json(IBGE_STATES_URL, timeout)
        cities_payload = self._download_json(IBGE_CITIES_URL, timeout)
        currencies_xml = self._download_bytes(ISO_CURRENCIES_URL, timeout)

        countries = self._parse_countries(countries_payload)
        states = self._parse_states(states_payload)
        cities = self._parse_cities(cities_payload, states)
        currencies = self._parse_currencies(currencies_xml)
        counts = {
            'countries': len(countries),
            'states': len(states),
            'cities': len(cities),
            'currencies': len(currencies),
        }
        if not options['allow_partial']:
            self._validate_cardinality(counts)

        with transaction.atomic():
            country_refs = self._upsert_countries(countries)
            brazil = country_refs.get('Brasil')
            state_refs = self._upsert_states(states, brazil)
            self._upsert_cities(cities, state_refs)
            self._upsert_currencies(currencies)

        summary = (
            f'Carga oficial concluída: países={counts["countries"]}, '
            f'UFs={counts["states"]}, municípios={counts["cities"]}, '
            f'moedas={counts["currencies"]}.'
        )
        LOGGER.info(summary)
        self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _download_json(url, timeout):
        response = Command._request(url, timeout)
        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise CommandError(f'Resposta JSON inválida recebida de {url}.') from error
        if not isinstance(payload, list):
            raise CommandError(f'Formato inesperado recebido de {url}.')
        return payload

    @staticmethod
    def _download_bytes(url, timeout):
        return Command._request(url, timeout).content

    @staticmethod
    def _request(url, timeout):
        try:
            response = requests.get(
                url,
                headers={'User-Agent': 'RGNFarmaSystem/1.0 reference-data-loader'},
                timeout=(10, timeout),
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise CommandError(f'Falha ao obter a fonte oficial {url}: {error}') from error
        if len(response.content) > 20 * 1024 * 1024:
            raise CommandError(f'Resposta excede o limite de 20 MiB: {url}.')
        return response

    @staticmethod
    def _parse_countries(payload):
        countries = {}
        for item in payload:
            name = str(item.get('nome') or '').strip() if isinstance(item, dict) else ''
            if not name:
                raise CommandError('País com identificação inválida recebido do IBGE.')
            identifier = item.get('id') or {}
            alpha2 = str(identifier.get('ISO-ALPHA-2') or '').strip().upper()
            alpha3 = str(identifier.get('ISO-ALPHA-3') or '').strip().upper()
            numeric = str(identifier.get('M49') or '').strip()
            countries[name] = {
                'name': name,
                'iso_alpha2': alpha2,
                'iso_alpha3': alpha3,
                'numeric_code': numeric.zfill(3) if numeric else '',
            }
        if 'Brasil' not in countries:
            raise CommandError('Fonte IBGE sem o registro do Brasil.')
        return countries

    @staticmethod
    def _parse_states(payload):
        states = {}
        for item in payload:
            if not isinstance(item, dict):
                raise CommandError('UF com formato inválido recebida do IBGE.')
            numeric_code = str(item.get('id') or '')
            abbreviation = str(item.get('sigla') or '').strip().upper()
            name = str(item.get('nome') or '').strip()
            if len(abbreviation) != 2 or len(numeric_code) != 2 or not name:
                raise CommandError('UF com identificação inválida recebida do IBGE.')
            if abbreviation in states:
                raise CommandError(f'UF duplicada na fonte do IBGE: {abbreviation}.')
            states[abbreviation] = {
                'name': name,
                'abbreviation': abbreviation,
                'numeric_code': numeric_code,
            }
        return states

    @classmethod
    def _parse_cities(cls, payload, states):
        state_by_numeric = {state['numeric_code']: code for code, state in states.items()}
        cities = {}
        for item in payload:
            if not isinstance(item, dict):
                raise CommandError('Município com formato inválido recebido do IBGE.')
            ibge_code = str(item.get('id') or '')
            name = str(item.get('nome') or '').strip()
            abbreviation = cls._city_state_abbreviation(item)
            if not abbreviation and len(ibge_code) == 7:
                abbreviation = state_by_numeric.get(ibge_code[:2], '')
            if abbreviation not in states:
                label = abbreviation or 'desconhecida'
                raise CommandError(f'UF {label} não encontrada para o município {ibge_code}.')
            if len(ibge_code) != 7 or not ibge_code.isdigit() or not name:
                raise CommandError('Município com identificação inválida recebido do IBGE.')
            if ibge_code in cities:
                raise CommandError(f'Município duplicado na fonte do IBGE: {ibge_code}.')
            cities[ibge_code] = {
                'name': name,
                'state': abbreviation,
                'ibge_code': ibge_code,
            }
        return cities

    @staticmethod
    def _city_state_abbreviation(item):
        paths = (
            ('regiao-imediata', 'regiao-intermediaria', 'UF'),
            ('microrregiao', 'mesorregiao', 'UF'),
        )
        for path in paths:
            value = item
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, dict) and value.get('sigla'):
                return str(value['sigla']).strip().upper()
        return ''

    @staticmethod
    def _parse_currencies(payload):
        try:
            root = ElementTree.fromstring(payload)
        except (ElementTree.ParseError, ValueError) as error:
            raise CommandError('XML inválido recebido da ISO 4217/SIX.') from error
        published_at = str(root.attrib.get('Pblshd') or 'data não informada')
        currencies = {}
        entities = defaultdict(set)
        for item in root.findall('.//CcyNtry'):
            code = (item.findtext('Ccy') or '').strip().upper()
            if not code:
                continue
            name = (item.findtext('CcyNm') or '').strip()
            numeric_code = (item.findtext('CcyNbr') or '').strip()
            minor_units = (item.findtext('CcyMnrUnts') or '').strip()
            entity = (item.findtext('CtryNm') or '').strip()
            if len(code) != 3 or not code.isalpha() or not name:
                raise CommandError(f'Moeda com identificação inválida na fonte ISO 4217: {code}.')
            if len(numeric_code) != 3 or not numeric_code.isdigit():
                raise CommandError(f'Código numérico inválido para a moeda {code}.')
            decimal_places = int(minor_units) if minor_units.isdigit() else 0
            current = currencies.get(code)
            values = (name, numeric_code, decimal_places)
            if current and current != values:
                raise CommandError(f'Dados divergentes para a moeda {code} na fonte ISO 4217.')
            currencies[code] = values
            if entity:
                entities[code].add(entity)

        return {
            code: {
                'code': code,
                'name': str(get_currency_name(code, locale='pt_BR') or values[0]).strip(),
                'numeric_code': values[1],
                'decimal_places': values[2],
                'symbol': CURRENCY_SYMBOLS.get(code, ''),
                'description': (
                    f'Entidades usuárias: {"; ".join(sorted(entities[code]))}. '
                    f'Fonte: ISO 4217/SIX (lista vigente em {published_at}).'
                ),
            }
            for code, values in currencies.items()
        }

    @staticmethod
    def _validate_cardinality(counts):
        for catalog, minimum in EXPECTED_MINIMUMS.items():
            if counts[catalog] < minimum:
                raise CommandError(
                    f'Fonte incompleta para {catalog}: {counts[catalog]} registros; '
                    f'mínimo esperado={minimum}.'
                )

    @staticmethod
    def _single_or_none(queryset, label):
        matches = list(queryset.order_by('pk')[:2])
        if len(matches) > 1:
            raise CommandError(f'Mais de um cadastro local corresponde a {label}.')
        return matches[0] if matches else None

    def _upsert_countries(self, countries):
        refs = {}
        for name, data in countries.items():
            obj = self._single_or_none(
                Country.objects.filter(name=name),
                f'país {name}',
            )
            if obj is None:
                obj = Country()
            self._save_location_fields(
                obj,
                data,
                code_fields=('iso_alpha2', 'iso_alpha3', 'numeric_code'),
                label=f'país {name}',
            )
            refs[name] = obj
        return refs

    def _upsert_states(self, states, country_obj):
        refs = {}
        for code, data in states.items():
            name = data['name']
            obj = self._single_or_none(
                StateProvince.objects.filter(country=country_obj, name=name),
                f'UF {data["abbreviation"]}',
            )
            if obj is None:
                obj = StateProvince()
            self._save_location_fields(
                obj,
                {
                    'name': name,
                    'country': country_obj,
                    'abbreviation': data['abbreviation'],
                    'ibge_code': data['numeric_code'],
                },
                code_fields=('abbreviation', 'ibge_code'),
                label=f'UF {data["abbreviation"]}',
            )
            refs[code] = obj
        return refs

    def _upsert_cities(self, cities, state_refs):
        for code, data in cities.items():
            name = data['name']
            state_obj = state_refs[data['state']]
            obj = self._single_or_none(
                City.objects.filter(state=state_obj, name=name),
                f'município {data["ibge_code"]}',
            )
            if obj is None:
                obj = City()
            self._save_location_fields(
                obj,
                {
                    'name': name,
                    'state': state_obj,
                    'ibge_code': data['ibge_code'],
                },
                code_fields=('ibge_code',),
                label=f'município {data["ibge_code"]}',
            )

    def _upsert_currencies(self, currencies):
        for code, data in currencies.items():
            obj = self._single_or_none(
                Currency.objects.filter(Q(code=code) | Q(numeric_code=data['numeric_code'])),
                f'moeda {code}',
            )
            if obj is None:
                obj = Currency(code=code)
            self._save_fields(obj, data)

    @staticmethod
    def _save_fields(obj, fields):
        for field, value in fields.items():
            if field != 'code' or not obj.pk:
                setattr(obj, field, value)
        obj.is_active = True
        obj.full_clean()
        obj.save()

    @staticmethod
    def _save_location_fields(obj, fields, *, code_fields, label):
        for field in code_fields:
            existing_value = getattr(obj, field)
            official_value = fields[field]
            if existing_value and existing_value != official_value:
                raise CommandError(
                    f'Código oficial divergente para {label}: '
                    f'{field} local={existing_value!r}, fonte={official_value!r}.'
                )

        if obj.pk:
            for field in code_fields:
                if not getattr(obj, field):
                    setattr(obj, field, fields[field])
        else:
            for field, value in fields.items():
                setattr(obj, field, value)
        obj.full_clean()
        obj.save()
