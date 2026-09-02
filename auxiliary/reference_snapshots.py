from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from django.core.management.base import CommandError
from django.db import transaction

from auxiliary.models import City, Country, Currency, StateProvince
from reference_data.manifest import CatalogManifest


REQUIRED_SECTIONS = {'countries', 'states', 'cities', 'currencies'}
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / 'reference_data'
    / 'snapshots'
    / 'official_references.json'
)
DEFAULT_MANIFEST_PATH = DEFAULT_SNAPSHOT_PATH.with_name('official_references.manifest.json')


@dataclass(frozen=True)
class OfficialReferenceSnapshot:
    manifest: CatalogManifest
    payload: dict[str, list[dict[str, Any]]]


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except OSError as error:
        raise CommandError(f'Não foi possível ler {label}: {path}.') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CommandError(f'{label.capitalize()} possui JSON inválido: {path}.') from error


def load_official_snapshot(
    path: Path | None = None,
    manifest_path: Path | None = None,
) -> OfficialReferenceSnapshot:
    snapshot_path = Path(path) if path is not None else DEFAULT_SNAPSHOT_PATH
    if manifest_path is None:
        manifest_file = (
            snapshot_path.with_name('official_references.manifest.json')
            if path is not None
            else DEFAULT_MANIFEST_PATH
        )
    else:
        manifest_file = Path(manifest_path)

    payload = _load_json(snapshot_path, 'snapshot oficial')
    manifest_payload = _load_json(manifest_file, 'manifesto oficial')
    if not isinstance(manifest_payload, dict):
        raise CommandError('Manifesto oficial deve ser um objeto JSON.')
    try:
        manifest = CatalogManifest.from_dict(manifest_payload)
        manifest.validate_payload(payload)
    except ValueError as error:
        raise CommandError(str(error)) from error

    if not isinstance(payload, dict) or set(payload) != REQUIRED_SECTIONS:
        raise CommandError('Snapshot oficial possui seções ausentes ou inesperadas.')
    if set(manifest.expected_counts) != REQUIRED_SECTIONS:
        raise CommandError('Manifesto oficial possui contagens ausentes ou inesperadas.')
    for section, expected in manifest.expected_counts.items():
        records = payload[section]
        if not isinstance(records, list):
            raise CommandError(f'Seção inválida no snapshot: {section}.')
        if len(records) != expected:
            raise CommandError(f'Contagem divergente no snapshot: {section}.')
        if not all(isinstance(record, dict) for record in records):
            raise CommandError(f'Registro inválido no snapshot: {section}.')

    return OfficialReferenceSnapshot(manifest=manifest, payload=payload)


def _single_or_none(queryset, label):
    matches = list(queryset.order_by('pk')[:2])
    if len(matches) > 1:
        raise CommandError(f'Mais de um cadastro local corresponde a {label}.')
    return matches[0] if matches else None


def _text(record: dict[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f'{label} possui o campo {field} inválido.')
    return value.strip()


def _ensure_location_codes(
    obj,
    fields: dict[str, Any],
    *,
    code_fields: tuple[str, ...],
    label: str,
) -> None:
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


def _ensure_code_available(queryset, *, field: str, value: str, obj, label: str) -> None:
    conflicting = queryset.filter(**{field: value})
    if obj.pk:
        conflicting = conflicting.exclude(pk=obj.pk)
    if conflicting.exists():
        raise CommandError(f'Código oficial já pertence a outro {label}: {field}={value!r}.')


def _apply_countries(records: list[dict[str, Any]]) -> dict[str, Country]:
    refs = {}
    for record in records:
        name = _text(record, 'name', 'País')
        fields = {
            'name': name,
            'iso_alpha2': _text(record, 'iso_alpha2', f'País {name}').upper(),
            'iso_alpha3': _text(record, 'iso_alpha3', f'País {name}').upper(),
            'numeric_code': _text(record, 'numeric_code', f'País {name}'),
        }
        obj = _single_or_none(Country.objects.filter(name=name), f'país {name}') or Country()
        for field in ('iso_alpha2', 'iso_alpha3', 'numeric_code'):
            _ensure_code_available(
                Country.objects,
                field=field,
                value=fields[field],
                obj=obj,
                label='país',
            )
        _ensure_location_codes(
            obj,
            fields,
            code_fields=('iso_alpha2', 'iso_alpha3', 'numeric_code'),
            label=f'país {name}',
        )
        refs[fields['iso_alpha2']] = obj
    return refs


def _apply_states(
    records: list[dict[str, Any]],
    country_refs: dict[str, Country],
) -> dict[str, StateProvince]:
    refs = {}
    for record in records:
        name = _text(record, 'name', 'UF')
        abbreviation = _text(record, 'abbreviation', f'UF {name}').upper()
        ibge_code = _text(record, 'ibge_code', f'UF {abbreviation}')
        country_code = _text(record, 'country_iso_alpha2', f'UF {abbreviation}').upper()
        country = country_refs.get(country_code)
        if country is None:
            raise CommandError(f'País {country_code} não encontrado para a UF {abbreviation}.')
        obj = (
            _single_or_none(
                StateProvince.objects.filter(country=country, name=name),
                f'UF {abbreviation}',
            )
            or StateProvince()
        )
        _ensure_code_available(
            StateProvince.objects.filter(country=country),
            field='abbreviation',
            value=abbreviation,
            obj=obj,
            label='cadastro de UF',
        )
        _ensure_code_available(
            StateProvince.objects,
            field='ibge_code',
            value=ibge_code,
            obj=obj,
            label='cadastro de UF',
        )
        _ensure_location_codes(
            obj,
            {
                'name': name,
                'abbreviation': abbreviation,
                'ibge_code': ibge_code,
                'country': country,
            },
            code_fields=('abbreviation', 'ibge_code'),
            label=f'UF {abbreviation}',
        )
        refs[ibge_code] = obj
    return refs


def _apply_cities(
    records: list[dict[str, Any]],
    state_refs: dict[str, StateProvince],
) -> None:
    for record in records:
        name = _text(record, 'name', 'Município')
        ibge_code = _text(record, 'ibge_code', f'Município {name}')
        state_code = _text(record, 'state_ibge_code', f'Município {ibge_code}')
        state = state_refs.get(state_code)
        if state is None:
            raise CommandError(f'UF {state_code} não encontrada para o município {ibge_code}.')
        obj = (
            _single_or_none(
                City.objects.filter(state=state, name=name),
                f'município {ibge_code}',
            )
            or City()
        )
        _ensure_code_available(
            City.objects,
            field='ibge_code',
            value=ibge_code,
            obj=obj,
            label='município',
        )
        _ensure_location_codes(
            obj,
            {'name': name, 'ibge_code': ibge_code, 'state': state},
            code_fields=('ibge_code',),
            label=f'município {ibge_code}',
        )


def _apply_currencies(records: list[dict[str, Any]]) -> None:
    for record in records:
        code = _text(record, 'code', 'Moeda').upper()
        fields = {
            'code': code,
            'name': _text(record, 'name', f'Moeda {code}'),
            'numeric_code': _text(record, 'numeric_code', f'Moeda {code}'),
            'symbol': record.get('symbol', ''),
            'decimal_places': record.get('decimal_places'),
            'description': record.get('description', ''),
        }
        if not isinstance(fields['symbol'], str) or not isinstance(fields['description'], str):
            raise CommandError(f'Moeda {code} possui texto inválido.')
        if not isinstance(fields['decimal_places'], int) or isinstance(
            fields['decimal_places'], bool
        ):
            raise CommandError(f'Moeda {code} possui casas decimais inválidas.')
        obj = _single_or_none(Currency.objects.filter(code=code), f'moeda {code}')
        if obj is None:
            if Currency.objects.filter(numeric_code=fields['numeric_code']).exists():
                raise CommandError(
                    'Código numérico oficial já pertence a outra moeda: '
                    f'numeric_code={fields["numeric_code"]!r}.'
                )
            obj = Currency(code=code)
        for field, value in fields.items():
            if field != 'code' or not obj.pk:
                setattr(obj, field, value)
        obj.is_active = True
        obj.full_clean()
        obj.save()


def apply_official_snapshot(snapshot: OfficialReferenceSnapshot) -> dict[str, int]:
    counts = {section: len(snapshot.payload[section]) for section in REQUIRED_SECTIONS}
    ordered_counts = {
        'countries': counts['countries'],
        'states': counts['states'],
        'cities': counts['cities'],
        'currencies': counts['currencies'],
    }
    with transaction.atomic():
        country_refs = _apply_countries(snapshot.payload['countries'])
        state_refs = _apply_states(snapshot.payload['states'], country_refs)
        _apply_cities(snapshot.payload['cities'], state_refs)
        _apply_currencies(snapshot.payload['currencies'])
    return ordered_counts
