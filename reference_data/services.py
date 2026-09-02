"""Serviços de aplicação coordenada dos dados de referência de produção."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from auxiliary.cosmetics_seed import (
    AUXILIARY_CATALOG_MANIFEST,
    seed_cosmetics_auxiliary_data,
    validate_cosmetics_auxiliary_data,
)
from auxiliary.reference_snapshots import apply_official_snapshot, load_official_snapshot
from reference_data.cosmetics_catalogs import COSMETICS_CATALOG_MANIFEST
from reference_data.loaders import apply_catalogs, validate_catalogs


@dataclass(frozen=True)
class ReferenceDataResult:
    manifest_hashes: dict[str, str]
    counts: dict[str, dict[str, int]]


def _normalize_counts(counts: dict[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items()))


@transaction.atomic
def seed_production_reference_data() -> ReferenceDataResult:
    """Aplica todos os catálogos versionados em uma única transação."""

    official = load_official_snapshot()
    validate_catalogs(include_auxiliary_dependencies=False)
    validate_cosmetics_auxiliary_data()
    official_counts = apply_official_snapshot(official, use_current_transaction=True)
    auxiliary_counts = seed_cosmetics_auxiliary_data(use_current_transaction=True)
    domain_counts = apply_catalogs(use_current_transaction=True)
    return ReferenceDataResult(
        manifest_hashes={
            official.manifest.identifier: official.manifest.canonical_hash(),
            AUXILIARY_CATALOG_MANIFEST.identifier: AUXILIARY_CATALOG_MANIFEST.canonical_hash(),
            COSMETICS_CATALOG_MANIFEST.identifier: COSMETICS_CATALOG_MANIFEST.canonical_hash(),
        },
        counts={
            'official': _normalize_counts(official_counts),
            'auxiliary': _normalize_counts(auxiliary_counts),
            **domain_counts,
        },
    )
