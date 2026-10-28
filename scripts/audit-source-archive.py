#!/usr/bin/env python3
"""Audit the final compressed archive against the actual corresponding sources.

Checks every file, entry type, mode and literal symlink target without extraction.
Git internals and build output are intentionally excluded from corresponding source.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import stat
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0-rc3-rebuild1'
ARCHIVE = ROOT / f'dist/ChatGPTKernel-{VERSION}-sources.tar.zst'
TOPS = ('README.md', 'STATUS.md', '.gitignore', '.gitattributes', '.github',
        'config', 'docs', 'patches', 'scripts', 'tests', 'installer',
        '.cache/linux', '.cache/kernelsu', '.cache/baseband-guard', '.cache/susfs',
        '.cache/prepared.json', '.cache/source-receipts', 'out/build-manifest.json')

def excluded(name):
    return any(part in ('.git', '__pycache__') for part in PurePosixPath(name).parts) or name.endswith('.pyc')

def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def expected_entries():
    result = {}
    def add(path):
        name = path.relative_to(ROOT).as_posix()
        if excluded(name):
            return
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        if path.is_symlink():
            result[name] = {'type': 'symlink', 'target': os.readlink(path), 'mode': mode}
        elif path.is_dir():
            result[name] = {'type': 'directory', 'mode': mode}
            for child in sorted(path.iterdir()):
                add(child)
        elif path.is_file():
            result[name] = {'type': 'file', 'bytes': metadata.st_size, 'sha256': digest_file(path), 'mode': mode}
        else:
            raise AssertionError(f'Unsupported source entry: {name}')
    for top in TOPS:
        add(ROOT / top)
    return result

def main():
    expected = expected_entries()
    process = subprocess.Popen(['zstd', '-d', '-c', str(ARCHIVE)], stdout=subprocess.PIPE)
    actual = {}
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                name = member.name.rstrip('/')
                assert name not in actual, f'Duplicate archive entry: {name}'
                assert name in expected and not excluded(name), f'Unexpected source entry: {name}'
                entry = {'mode': member.mode}
                if member.isfile():
                    stream = archive.extractfile(member)
                    entry.update(type='file', bytes=member.size, sha256=hashlib.file_digest(stream, 'sha256').hexdigest())
                elif member.isdir():
                    entry['type'] = 'directory'
                elif member.issym():
                    entry.update(type='symlink', target=member.linkname)
                else:
                    raise AssertionError(f'Unsupported archive entry type: {name}')
                assert entry == expected[name], f'Archive content/type/mode mismatch: {name}'
                actual[name] = entry
        assert process.wait() == 0, 'zstd decompression failed'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert actual == expected, f'Missing source entries: {sorted(expected.keys() - actual.keys())[:10]}'
    report = {'archive': ARCHIVE.name, 'sha256': digest_file(ARCHIVE),
              'entries': len(actual), 'all_contents_types_modes_and_symlink_targets_match': True,
              'component_entries': {name: sum(key == name or key.startswith(name + '/') for key in actual)
                                    for name in ('.cache/linux', '.cache/kernelsu', '.cache/baseband-guard')},
              'entries_manifest_sha256': hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()}
    (ROOT / 'dist/source-archive-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
