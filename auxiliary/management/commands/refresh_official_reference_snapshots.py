from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
import re

from babel.numbers import get_currency_name
from defusedxml import ElementTree
from django.core.management.base import BaseCommand, CommandError
import requests

from reference_data.currency_names_pt_br import CURRENCY_NAMES_PT_BR
from reference_data.manifest import build_manifest, write_snapshot


IBGE_COUNTRIES_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/paises?orderBy=nome'
IBGE_STATES_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome'
IBGE_CITIES_URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome'
ISO_CURRENCIES_URL = (
    'https://www.six-group.com/dam/download/financial-information/'
    'data-center/iso-currrency/lists/list-one.xml'
)

SOURCE_URLS = (
    IBGE_COUNTRIES_URL,
    IBGE_STATES_URL,
    IBGE_CITIES_URL,
    ISO_CURRENCIES_URL,
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
    help = 'Atualiza explicitamente o snapshot oficial a partir do IBGE e da ISO 4217/SIX.'

    def add_arguments(self, parser):
        # BaseCommand reserva --version para a versão do Django. Este comando precisa
        # desse nome como identificador obrigatório e versionado do artefato gerado.
        base_version = parser._option_string_actions['--version']
        parser._remove_action(base_version)
        parser._option_string_actions.pop('--version')
        for group in parser._action_groups:
            if base_version in group._group_actions:
                group._group_actions.remove(base_version)
        parser.add_argument('--version', required=True, help='Versão imutável do snapshot.')
        parser.add_argument(
            '--source-date',
            required=True,
            help='Data de corte das fontes no formato AAAA-MM-DD.',
        )
        parser.add_argument(
            '--output-dir',
            type=Path,
            required=True,
            help='Diretório de destino do snapshot e do manifesto.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=60,
            help='Tempo limite, em segundos, para cada requisição HTTPS.',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        if timeout < 1 or timeout > 300:
            raise CommandError('--timeout deve estar entre 1 e 300 segundos.')
        version = str(options['version']).strip()
        source_date = str(options['source_date']).strip()
        if not version:
            raise CommandError('--version não pode ser vazio.')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', source_date) is None:
            raise CommandError('--source-date deve usar o formato AAAA-MM-DD.')
        try:
            date.fromisoformat(source_date)
        except ValueError as error:
            raise CommandError('--source-date deve usar o formato AAAA-MM-DD.') from error

        payload = self.fetch_and_parse(timeout=timeout)
        self._validate_cardinality(payload)
        manifest = build_manifest(
            identifier='official-references-br',
            version=version,
            source_date=source_date,
            source_urls=SOURCE_URLS,
            namespaces=('ISO-3166', 'IBGE-LOCALIDADES', 'ISO-4217'),
            provenance=(
                'Países, UFs e municípios extraídos da API de Localidades do IBGE.',
                'Moedas extraídas da List One ISO 4217 publicada pela SIX Group.',
            ),
            license_name='Dados oficiais de acesso público das fontes citadas',
            license_url='https://servicodados.ibge.gov.br/api/docs/localidades',
            payload=payload,
        )
        output_dir = Path(options['output_dir'])
        snapshot_path = output_dir / 'official_references.json'
        manifest_path = output_dir / 'official_references.manifest.json'
        write_snapshot(snapshot_path, manifest_path, payload, manifest)
        counts = ', '.join(f'{key}={len(value)}' for key, value in payload.items())
        self.stdout.write(
            self.style.SUCCESS(
                f'Snapshot oficial atualizado: {counts}; '
                f'versão={manifest.version}; sha256={manifest.sha256}.'
            )
        )

    def fetch_and_parse(self, *, timeout: int) -> dict[str, list[dict]]:
        countries = self._parse_countries(self._download_json(IBGE_COUNTRIES_URL, timeout))
        states = self._parse_states(self._download_json(IBGE_STATES_URL, timeout))
        cities = self._parse_cities(
            self._download_json(IBGE_CITIES_URL, timeout),
            states,
        )
        currencies = self._parse_currencies(self._download_bytes(ISO_CURRENCIES_URL, timeout))
        return {
            'countries': countries,
            'states': states,
            'cities': cities,
            'currencies': currencies,
        }

    @staticmethod
    def _download_json(url, timeout):
        response = Command._request(url, timeout)
        try:
            payload = response.json()
        except (requests.exceptions.JSONDecodeError, ValueError) as error:
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
                headers={'User-Agent': 'RGNFarmaSystem/1.0 reference-snapshot-refresh'},
                timeout=(min(10, timeout), timeout),
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
            identifier = item.get('id') or {} if isinstance(item, dict) else {}
            alpha2 = str(identifier.get('ISO-ALPHA-2') or '').strip().upper()
            alpha3 = str(identifier.get('ISO-ALPHA-3') or '').strip().upper()
            numeric = str(identifier.get('M49') or '').strip()
            if (
                not name
                or len(alpha2) != 2
                or len(alpha3) != 3
                or not numeric.isdigit()
                or len(numeric) > 3
            ):
                raise CommandError('País com identificação inválida recebido do IBGE.')
            if alpha2 in countries:
                raise CommandError(f'País duplicado na fonte do IBGE: {alpha2}.')
            countries[alpha2] = {
                'name': name,
                'iso_alpha2': alpha2,
                'iso_alpha3': alpha3,
                'numeric_code': numeric.zfill(3),
            }
        if 'BR' not in countries:
            raise CommandError('Fonte IBGE sem o registro do Brasil.')
        return sorted(countries.values(), key=lambda item: item['iso_alpha2'])

    @staticmethod
    def _parse_states(payload):
        states = {}
        for item in payload:
            if not isinstance(item, dict):
                raise CommandError('UF com formato inválido recebida do IBGE.')
            ibge_code = str(item.get('id') or '')
            abbreviation = str(item.get('sigla') or '').strip().upper()
            name = str(item.get('nome') or '').strip()
            if len(abbreviation) != 2 or len(ibge_code) != 2 or not name:
                raise CommandError('UF com identificação inválida recebida do IBGE.')
            if ibge_code in states:
                raise CommandError(f'UF duplicada na fonte do IBGE: {ibge_code}.')
            states[ibge_code] = {
                'name': name,
                'abbreviation': abbreviation,
                'ibge_code': ibge_code,
                'country_iso_alpha2': 'BR',
            }
        return sorted(states.values(), key=lambda item: item['ibge_code'])

    @classmethod
    def _parse_cities(cls, payload, states):
        state_codes = {state['ibge_code'] for state in states}
        cities = {}
        for item in payload:
            if not isinstance(item, dict):
                raise CommandError('Município com formato inválido recebido do IBGE.')
            ibge_code = str(item.get('id') or '')
            name = str(item.get('nome') or '').strip()
            state_code = cls._city_state_code(item)
            if not state_code and len(ibge_code) == 7:
                state_code = ibge_code[:2]
            if state_code not in state_codes:
                label = state_code or 'desconhecida'
                raise CommandError(f'UF {label} não encontrada para o município {ibge_code}.')
            if len(ibge_code) != 7 or not ibge_code.isdigit() or not name:
                raise CommandError('Município com identificação inválida recebido do IBGE.')
            if ibge_code in cities:
                raise CommandError(f'Município duplicado na fonte do IBGE: {ibge_code}.')
            cities[ibge_code] = {
                'name': name,
                'state_ibge_code': state_code,
                'ibge_code': ibge_code,
            }
        return sorted(cities.values(), key=lambda item: item['ibge_code'])

    @staticmethod
    def _city_state_code(item):
        paths = (
            ('regiao-imediata', 'regiao-intermediaria', 'UF'),
            ('microrregiao', 'mesorregiao', 'UF'),
        )
        for path in paths:
            value = item
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, dict) and value.get('id') is not None:
                return str(value['id'])
        return ''

    @staticmethod
    def _parse_currencies(payload):
        try:
            root = ElementTree.fromstring(payload)
        except (ElementTree.ParseError, ValueError) as error:
            raise CommandError('XML inválido recebido da ISO 4217/SIX.') from error
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
            if minor_units == 'N.A.':
                decimal_places = 0
                minor_unit_applicable = False
            elif minor_units.isdigit():
                decimal_places = int(minor_units)
                minor_unit_applicable = True
            else:
                raise CommandError(
                    f'Valor de unidade menor inválido para a moeda {code}: {minor_units!r}.'
                )
            current = currencies.get(code)
            values = (name, numeric_code, decimal_places, minor_unit_applicable)
            if current and current != values:
                raise CommandError(f'Dados divergentes para a moeda {code} na fonte ISO 4217.')
            currencies[code] = values
            if entity:
                entities[code].add(entity)
        duplicated_numeric = defaultdict(list)
        for code, values in currencies.items():
            duplicated_numeric[values[1]].append(code)
        conflicts = sorted(
            (numeric, sorted(codes))
            for numeric, codes in duplicated_numeric.items()
            if len(codes) > 1
        )
        if conflicts:
            details = '; '.join(
                f'numeric_code={numeric!r}: {", ".join(codes)}' for numeric, codes in conflicts
            )
            raise CommandError(f'Código numérico duplicado na fonte ISO 4217: {details}.')

        records = []
        for code, values in currencies.items():
            localized_name = str(get_currency_name(code, locale='pt_BR') or '').strip()
            display_name = CURRENCY_NAMES_PT_BR.get(code, localized_name)
            if not display_name or display_name == code:
                raise CommandError(
                    f'Moeda {code} sem nome pt-BR no CLDR ou na tabela explícita revisada.'
                )
            records.append(
                {
                    'code': code,
                    'name': display_name,
                    'numeric_code': values[1],
                    'decimal_places': values[2],
                    'minor_unit_applicable': values[3],
                    'symbol': CURRENCY_SYMBOLS.get(code, ''),
                    'source_name': values[0],
                    'source_entities': sorted(entities[code]),
                    'description': 'Moeda ISO 4217 com nome localizado para português do Brasil.',
                }
            )
        return sorted(records, key=lambda item: item['code'])

    @staticmethod
    def _validate_cardinality(payload):
        for catalog, minimum in EXPECTED_MINIMUMS.items():
            count = len(payload[catalog])
            if catalog == 'states' and count != minimum:
                raise CommandError(f'Fonte incompleta para states: {count} registros; esperado=27.')
            if catalog != 'states' and count < minimum:
                raise CommandError(
                    f'Fonte incompleta para {catalog}: {count} registros; '
                    f'mínimo esperado={minimum}.'
                )
