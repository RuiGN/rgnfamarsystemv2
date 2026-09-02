from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


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

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['source_urls'] = list(self.source_urls)
        payload['namespaces'] = list(self.namespaces)
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
        }
        if set(payload) != required_fields:
            raise ValueError('Manifesto oficial possui campos ausentes ou inesperados.')
        if not isinstance(payload['source_urls'], list) or not all(
            isinstance(url, str) and url for url in payload['source_urls']
        ):
            raise ValueError('Manifesto oficial possui URLs de fonte inválidas.')
        if not isinstance(payload['namespaces'], list) or not all(
            isinstance(namespace, str) and namespace for namespace in payload['namespaces']
        ):
            raise ValueError('Manifesto oficial possui namespaces inválidos.')
        counts = payload['expected_counts']
        if not isinstance(counts, dict) or not all(
            isinstance(section, str)
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
            for section, count in counts.items()
        ):
            raise ValueError('Manifesto oficial possui contagens inválidas.')
        scalar_fields = ('identifier', 'version', 'source_date', 'sha256')
        if not all(isinstance(payload[field], str) and payload[field] for field in scalar_fields):
            raise ValueError('Manifesto oficial possui metadados inválidos.')
        if len(payload['sha256']) != 64:
            raise ValueError('Manifesto oficial possui SHA-256 inválido.')
        return cls(
            identifier=payload['identifier'],
            version=payload['version'],
            source_date=payload['source_date'],
            source_urls=tuple(payload['source_urls']),
            namespaces=tuple(payload['namespaces']),
            expected_counts=dict(counts),
            sha256=payload['sha256'],
        )

    def canonical_hash(self) -> str:
        return payload_hash(self.as_dict())

    def validate_payload(self, payload: Any) -> None:
        if payload_hash(payload) != self.sha256:
            raise ValueError('O SHA-256 do snapshot oficial não corresponde ao manifesto.')


def build_manifest(
    *,
    identifier: str,
    version: str,
    source_date: str,
    source_urls: tuple[str, ...],
    namespaces: tuple[str, ...],
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
    )


def write_snapshot(
    snapshot_path: Path,
    manifest_path: Path,
    payload: dict[str, Any],
    manifest: CatalogManifest,
) -> None:
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
