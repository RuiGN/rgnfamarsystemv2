import json
from pathlib import Path

import pytest

from reference_data.manifest import CatalogManifest, payload_hash, write_snapshot


PAYLOAD = {'catalog': [{'code': 'REF-1', 'name': 'Referência'}]}


def _manifest(**overrides):
    values = {
        'identifier': 'test-reference-catalog',
        'version': '2026.1',
        'source_date': '2026-09-02',
        'source_urls': ('https://example.test/catalog',),
        'namespaces': ('REF-',),
        'expected_counts': {'catalog': 1},
        'sha256': payload_hash(PAYLOAD),
        'provenance': ('Catálogo curado e revisado para o teste.',),
        'license_name': 'CC0-1.0',
        'license_url': 'https://creativecommons.org/publicdomain/zero/1.0/',
    }
    values.update(overrides)
    return CatalogManifest(**values)


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('source_date', '2026-02-30', 'data de fonte'),
        ('source_date', '20260902', 'data de fonte'),
        ('source_urls', ('http://example.test/catalog',), 'URLs de fonte'),
        ('source_urls', ('https:///catalog',), 'URLs de fonte'),
        ('namespaces', (), 'namespaces'),
        ('namespaces', ('REF-', ''), 'namespaces'),
        ('namespaces', ('REF-', 'REF-'), 'namespaces'),
        ('provenance', (), 'proveniência'),
        ('provenance', ('Catálogo curado.', ''), 'proveniência'),
        ('license_name', '', 'licença'),
        ('license_url', 'http://example.test/license', 'licença'),
    ],
)
def test_catalog_manifest_rejects_incomplete_or_invalid_metadata(field, value, message):
    with pytest.raises(ValueError, match=message):
        _manifest(**{field: value})


def test_catalog_manifest_keeps_payload_and_manifest_hashes_distinct():
    manifest = _manifest()

    assert manifest.sha256 == payload_hash(PAYLOAD)
    assert manifest.canonical_hash() == payload_hash(manifest.as_dict())
    assert manifest.canonical_hash() != manifest.sha256
    assert CatalogManifest.from_dict(manifest.as_dict()) == manifest


def test_write_snapshot_is_noop_for_identical_existing_version(tmp_path, monkeypatch):
    snapshot_path = tmp_path / 'catalog.json'
    manifest_path = tmp_path / 'catalog.manifest.json'
    manifest = _manifest()
    write_snapshot(snapshot_path, manifest_path, PAYLOAD, manifest)

    def reject_write(self, *args, **kwargs):
        raise AssertionError(f'escrita inesperada em {self}')

    monkeypatch.setattr(Path, 'write_text', reject_write)

    write_snapshot(snapshot_path, manifest_path, PAYLOAD, manifest)


@pytest.mark.parametrize('divergence', ['payload', 'metadata'])
def test_write_snapshot_refuses_divergent_existing_version(tmp_path, divergence):
    snapshot_path = tmp_path / 'catalog.json'
    manifest_path = tmp_path / 'catalog.manifest.json'
    manifest = _manifest()
    write_snapshot(snapshot_path, manifest_path, PAYLOAD, manifest)
    original_snapshot = snapshot_path.read_bytes()
    original_manifest = manifest_path.read_bytes()

    if divergence == 'payload':
        changed_payload = {'catalog': [{'code': 'REF-1', 'name': 'Alterada'}]}
        replacement = _manifest(sha256=payload_hash(changed_payload))
    else:
        changed_payload = PAYLOAD
        replacement = _manifest(version='2026.2')

    with pytest.raises(ValueError, match='recusa sobrescrever'):
        write_snapshot(snapshot_path, manifest_path, changed_payload, replacement)

    assert snapshot_path.read_bytes() == original_snapshot
    assert manifest_path.read_bytes() == original_manifest
    assert json.loads(snapshot_path.read_text(encoding='utf-8')) == PAYLOAD
