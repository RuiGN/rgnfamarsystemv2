import io
import tarfile

import pytest

from scripts.restore_media import UnsafeArchiveError, restore_media


def _write_archive(path, entries):
    with tarfile.open(path, 'w:gz') as archive:
        for name, content in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def test_restore_media_replaces_local_directory(tmp_path):
    archive = tmp_path / 'media.tar.gz'
    destination = tmp_path / 'media'
    destination.mkdir()
    (destination / 'obsolete.txt').write_text('old', encoding='utf-8')
    _write_archive(archive, [('./documents/evidence.txt', b'validated evidence')])

    restore_media(archive, destination)

    assert not (destination / 'obsolete.txt').exists()
    assert (destination / 'documents/evidence.txt').read_bytes() == b'validated evidence'
    assert not list(tmp_path.glob('.media.restore-*'))
    assert not list(tmp_path.glob('.media.previous-*'))


def test_restore_media_rejects_path_traversal_without_changing_destination(tmp_path):
    archive = tmp_path / 'malicious.tar.gz'
    destination = tmp_path / 'media'
    destination.mkdir()
    (destination / 'retained.txt').write_text('retain', encoding='utf-8')
    _write_archive(archive, [('../../outside.txt', b'unsafe')])

    with pytest.raises(UnsafeArchiveError, match='Caminho inseguro'):
        restore_media(archive, destination)

    assert (destination / 'retained.txt').read_text(encoding='utf-8') == 'retain'
    assert not (tmp_path / 'outside.txt').exists()


def test_restore_media_dry_run_validates_without_changing_destination(tmp_path):
    archive = tmp_path / 'media.tar.gz'
    destination = tmp_path / 'media'
    destination.mkdir()
    (destination / 'retained.txt').write_text('retain', encoding='utf-8')
    _write_archive(archive, [('./new.txt', b'new')])

    restore_media(archive, destination, dry_run=True)

    assert (destination / 'retained.txt').exists()
    assert not (destination / 'new.txt').exists()
