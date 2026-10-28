#!/usr/bin/env python3
"""Exercise real archive extraction, provenance and refusal of unsafe/reused inputs."""
from pathlib import Path
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from source_archive import extract_source, sha256, tree_digest
spec = importlib.util.spec_from_file_location('fetch_sources', ROOT / 'scripts/fetch-sources.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
COMMIT = '1' * 40


class SourceAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def archive(self, members=None):
        archive = self.root / 'input.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            for name, kind, value in members or [
                (f'project-{COMMIT}/file.c', 'file', b'original source\n'),
                (f'project-{COMMIT}/nested/link', 'link', '../file.c'),
            ]:
                info = tarfile.TarInfo(name)
                if kind == 'link':
                    info.type = tarfile.SYMTYPE
                    info.linkname = value
                    output.addfile(info)
                else:
                    info.size = len(value)
                    output.addfile(info, io.BytesIO(value))
        return archive

    def test_archive_fallback_records_bytes_hash_and_no_git_history(self):
        archive = self.archive()
        entry = {'repository': 'https://github.com/example/project.git', 'commit': COMMIT,
                 'archive_url': 'https://codeload.github.com/example/project/tar.gz/' + COMMIT,
                 'archive_sha256': sha256(archive)}
        def download(url, destination, digest):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, destination)
        with patch.object(fetch, 'run', side_effect=subprocess.CalledProcessError(128, 'git')), \
                patch.object(fetch, 'download', side_effect=download):
            result = fetch.acquire_source(entry, 'linux', cache=self.root / 'cache')
        receipt = json.loads((self.root / 'cache/source-receipts/linux.json').read_text())
        self.assertEqual(receipt['method'], 'immutable-archive')
        self.assertEqual(receipt['archive_sha256'], entry['archive_sha256'])
        self.assertEqual(receipt['tree_sha256'], tree_digest(result))
        self.assertFalse(receipt['git_history_present'])
        self.assertFalse((result / '.git').exists())
        self.assertEqual((result / 'nested/link').readlink().as_posix(), '../file.c')
        self.assertEqual((result / 'nested/link').read_bytes(), b'original source\n')
        (result / 'file.c').write_bytes(b'changed after acquisition\n')
        with self.assertRaisesRegex(RuntimeError, 'changed after acquisition'):
            fetch.acquire_source(entry, 'linux', cache=self.root / 'cache')

    def test_checksum_mismatch_leaves_destination_absent(self):
        archive = self.archive()
        destination = self.root / 'source'
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            extract_source(archive, destination, COMMIT, '0' * 64)
        self.assertFalse(destination.exists())

    def test_traversal_and_escaping_links_are_rejected_before_extraction(self):
        for name, kind, value in [
            (f'project-{COMMIT}/../escaped', 'file', b'bad'),
            (f'project-{COMMIT}/link', 'link', '../../escaped'),
            (f'project-{COMMIT}/.git/config', 'file', b'fake Git'),
        ]:
            with self.subTest(name=name):
                archive = self.archive([(name, kind, value)])
                with self.assertRaises(ValueError):
                    extract_source(archive, self.root / 'source', COMMIT, sha256(archive))
                self.assertFalse((self.root / 'source').exists())
                self.assertFalse((self.root / 'escaped').exists())

    def test_wrong_commit_root_and_duplicate_members_are_rejected(self):
        for members in [[('project-wrong/file.c', 'file', b'bad')],
                        [(f'project-{COMMIT}/file.c', 'file', b'one'),
                         (f'project-{COMMIT}/file.c', 'file', b'two')]]:
            archive = self.archive(members)
            with self.assertRaises(ValueError):
                extract_source(archive, self.root / 'source', COMMIT, sha256(archive))
            self.assertFalse((self.root / 'source').exists())

    def test_existing_tree_is_never_replaced_or_silently_trusted(self):
        archive = self.archive()
        destination = self.root / 'source'
        destination.mkdir()
        original = destination / 'valuable-work'
        original.write_bytes(b'keep this work')
        with self.assertRaises(FileExistsError):
            extract_source(archive, destination, COMMIT, sha256(archive))
        self.assertEqual(original.read_bytes(), b'keep this work')
        with self.assertRaises(subprocess.CalledProcessError):
            fetch.acquire_source({'commit': COMMIT}, 'source', cache=self.root)
        self.assertEqual(original.read_bytes(), b'keep this work')


if __name__ == '__main__':
    unittest.main()
