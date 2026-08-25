#!/usr/bin/env python3
"""Restore a media tarball locally with traversal checks and an atomic swap."""

from __future__ import annotations

import argparse
import os
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


class UnsafeArchiveError(ValueError):
    pass


def _safe_relative_path(member: tarfile.TarInfo) -> Path | None:
    name = member.name.removeprefix('./')
    if name in {'', '.'}:
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise UnsafeArchiveError(f'Caminho inseguro no artefato de mídia: {member.name}')
    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
        raise UnsafeArchiveError(f'Tipo de entrada não permitido: {member.name}')
    if not member.isdir() and not member.isfile():
        raise UnsafeArchiveError(f'Tipo de entrada desconhecido: {member.name}')
    return Path(*path.parts)


def validate_archive(archive: Path) -> list[tuple[tarfile.TarInfo, Path | None]]:
    with tarfile.open(archive, mode='r:gz') as source:
        members = [(member, _safe_relative_path(member)) for member in source.getmembers()]
    return members


def restore_media(archive: Path, destination: Path, *, dry_run: bool = False) -> None:
    members = validate_archive(archive)
    if dry_run:
        return

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{destination.name}.restore-', dir=destination.parent))
    previous = destination.parent / f'.{destination.name}.previous-{os.getpid()}'
    try:
        with tarfile.open(archive, mode='r:gz') as source:
            for member, relative_path in members:
                if relative_path is None:
                    continue
                target = staging / relative_path
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = source.extractfile(member)
                if extracted is None:
                    raise UnsafeArchiveError(f'Arquivo sem conteúdo: {member.name}')
                with extracted, target.open('wb') as output:
                    shutil.copyfileobj(extracted, output)

        if previous.exists():
            shutil.rmtree(previous)
        if destination.exists():
            destination.replace(previous)
        staging.replace(destination)
        if previous.exists():
            shutil.rmtree(previous)
    except Exception:
        if not destination.exists() and previous.exists():
            previous.replace(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    restore_media(args.archive, args.destination, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
