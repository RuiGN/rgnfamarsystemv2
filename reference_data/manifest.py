from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CatalogManifest:
    identifier: str
    version: str
    source_date: str
    source_urls: tuple[str, ...]
    namespaces: tuple[str, ...]
    expected_counts: dict[str, int]
    sha256: str
    provenance: tuple[str, ...]
    license_name: str
    license_url: str

    def __post_init__(self) -> None:
        scalar_fields = {
            'identificador': self.identifier,
            'versão': self.version,
            'licença': self.license_name,
        }
        if any(
            not isinstance(value, str) or value != value.strip() or not value
            for value in scalar_fields.values()
        ):
            raise ValueError('Manifesto possui identificador, versão ou licença inválida.')
        if not isinstance(self.source_date, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}', self.source_date
        ):
            raise ValueError('Manifesto possui data de fonte inválida; use YYYY-MM-DD.')
        try:
            date.fromisoformat(self.source_date)
        except ValueError as exc:
            raise ValueError('Manifesto possui data de fonte fora do calendário.') from exc
        self._validate_https_urls(self.source_urls, 'URLs de fonte')
        self._validate_https_urls((self.license_url,), 'URL de licença')
        if not self._valid_unique_strings(self.namespaces):
            raise ValueError('Manifesto possui namespaces vazios, inválidos ou duplicados.')
        if not self._valid_unique_strings(self.provenance):
            raise ValueError('Manifesto possui proveniência vazia, inválida ou duplicada.')
        if (
            not isinstance(self.expected_counts, dict)
            or not self.expected_counts
            or not all(
                isinstance(section, str)
                and section == section.strip()
                and bool(section)
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
                for section, count in self.expected_counts.items()
            )
        ):
            raise ValueError('Manifesto possui contagens inválidas.')
        if not isinstance(self.sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', self.sha256):
            raise ValueError('Manifesto possui SHA-256 de payload inválido.')

    @staticmethod
    def _valid_unique_strings(values: tuple[str, ...]) -> bool:
        return (
            isinstance(values, tuple)
            and bool(values)
            and all(
                isinstance(value, str) and value == value.strip() and bool(value)
                for value in values
            )
            and len(values) == len(set(values))
        )

    @classmethod
    def _validate_https_urls(cls, urls: tuple[str, ...], label: str) -> None:
        if not cls._valid_unique_strings(urls):
            raise ValueError(f'Manifesto possui {label} vazias, inválidas ou duplicadas.')
        for url in urls:
            try:
                parsed = urlsplit(url)
                valid_port = parsed.port is None or 1 <= parsed.port <= 65535
            except ValueError as exc:
                raise ValueError(f'Manifesto possui {label} inválidas.') from exc
            if (
                parsed.scheme != 'https'
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or any(character.isspace() for character in url)
                or not valid_port
            ):
                raise ValueError(f'Manifesto possui {label} inválidas.')

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['source_urls'] = list(self.source_urls)
        payload['namespaces'] = list(self.namespaces)
        payload['provenance'] = list(self.provenance)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CatalogManifest:
        required_fields = {
            'identifier',
            'version',
            'source_date',
            'source_urls',
            'namespaces',
            'expected_counts',
            'sha256',
            'provenance',
            'license_name',
            'license_url',
        }
        if set(payload) != required_fields:
            raise ValueError('Manifesto possui campos ausentes ou inesperados.')
        for field in ('source_urls', 'namespaces', 'provenance'):
            if not isinstance(payload[field], list):
                raise ValueError(f'Manifesto possui {field} inválido.')
        counts = payload['expected_counts']
        if not isinstance(counts, dict) or not all(
            isinstance(section, str)
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
            for section, count in counts.items()
        ):
            raise ValueError('Manifesto possui contagens inválidas.')
        return cls(
            identifier=payload['identifier'],
            version=payload['version'],
            source_date=payload['source_date'],
            source_urls=tuple(payload['source_urls']),
            namespaces=tuple(payload['namespaces']),
            expected_counts=dict(counts),
            sha256=payload['sha256'],
            provenance=tuple(payload['provenance']),
            license_name=payload['license_name'],
            license_url=payload['license_url'],
        )

    def canonical_hash(self) -> str:
        return payload_hash(self.as_dict())

    def validate_payload(self, payload: Any) -> None:
        if payload_hash(payload) != self.sha256:
            raise ValueError('O SHA-256 do payload não corresponde ao manifesto.')


def build_manifest(
    *,
    identifier: str,
    version: str,
    source_date: str,
    source_urls: tuple[str, ...],
    namespaces: tuple[str, ...],
    provenance: tuple[str, ...],
    license_name: str,
    license_url: str,
    payload: dict[str, Any],
) -> CatalogManifest:
    return CatalogManifest(
        identifier=identifier,
        version=version,
        source_date=source_date,
        source_urls=source_urls,
        namespaces=namespaces,
        expected_counts={section: len(records) for section, records in payload.items()},
        sha256=payload_hash(payload),
        provenance=provenance,
        license_name=license_name,
        license_url=license_url,
    )


def write_snapshot(
    snapshot_path: Path,
    manifest_path: Path,
    payload: dict[str, Any],
    manifest: CatalogManifest,
) -> None:
    manifest.validate_payload(payload)
    actual_counts = {section: len(records) for section, records in payload.items()}
    if actual_counts != manifest.expected_counts:
        raise ValueError('As contagens do payload divergem do manifesto.')

    existing_snapshot = snapshot_path.exists()
    existing_manifest = manifest_path.exists()
    if existing_snapshot != existing_manifest:
        raise ValueError('Snapshot existente está incompleto; recusa sobrescrever a versão.')
    if existing_snapshot:
        try:
            stored_payload = json.loads(snapshot_path.read_text(encoding='utf-8'))
            stored_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                'Snapshot existente é inválido; recusa sobrescrever a versão.'
            ) from exc
        if canonical_json(stored_payload) == canonical_json(payload) and canonical_json(
            stored_manifest
        ) == canonical_json(manifest.as_dict()):
            return
        raise ValueError('Snapshot existente diverge; recusa sobrescrever a versão.')

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    manifest_text = (
        json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    )
    snapshot_temporary = snapshot_path.with_suffix(f'{snapshot_path.suffix}.tmp')
    manifest_temporary = manifest_path.with_suffix(f'{manifest_path.suffix}.tmp')
    snapshot_temporary.write_text(snapshot_text, encoding='utf-8')
    manifest_temporary.write_text(manifest_text, encoding='utf-8')
    snapshot_temporary.replace(snapshot_path)
    manifest_temporary.replace(manifest_path)
