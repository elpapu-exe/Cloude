#!/usr/bin/env python3
"""Replay every patch against immutable original files, then compare results."""
from pathlib import Path
import argparse
import json
import subprocess
import tarfile
import tempfile
from source_archive import archive_root, sha256, tree_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/linux'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-tracked', action='store_true',
                        help='also compare all acquired final sources with kernel-source snapshots')
    options = parser.parse_args()
    patches = sorted((ROOT / 'patches').glob('*.patch'))
    files = set()
    original = set()
    for patch in patches:
        for line in patch.read_text().splitlines():
            if line.startswith('--- a/'):
                original.add(line[6:].split('\t', 1)[0])
            if line.startswith(('--- a/', '+++ b/')):
                name = line[6:].split('\t', 1)[0]
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Unsafe patch path')
                files.add(name)
    receipt = json.loads((ROOT / '.cache/source-receipts/linux.json').read_text())
    lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
    if receipt['commit'] != lock['kernel']['commit']:
        raise RuntimeError('Wrong original source commit')
    with tempfile.TemporaryDirectory() as directory:
        check = Path(directory)
        if receipt['method'] == 'git':
            for name in original:
                target = check / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(subprocess.check_output(
                    ['git', 'show', f'{receipt["commit"]}:{name}'], cwd=SOURCE))
        elif receipt['method'] == 'immutable-archive':
            archive = ROOT / '.cache/source-archives' / f'linux-{receipt["commit"]}.tar.gz'
            if sha256(archive) != receipt['archive_sha256']:
                raise RuntimeError('Original source archive changed')
            with tarfile.open(archive) as package:
                prefix = archive_root(package, receipt['commit'])
                for name in original:
                    member = package.getmember(prefix + '/' + name)
                    if not member.isfile():
                        raise RuntimeError(f'Expected regular original source: {name}')
                    target = check / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(package.extractfile(member).read())
        else:
            raise RuntimeError('Unsupported acquisition method')
        for patch in patches:
            subprocess.run(['patch', '--fuzz=0', '-p1', '-i', str(patch)], cwd=check,
                           check=True, stdout=subprocess.DEVNULL)
        for name in files:
            result, built = check / name, SOURCE / name
            if result.exists() != built.exists() or (result.exists() and result.read_bytes() != built.read_bytes()):
                raise RuntimeError(f'Unrecorded source edit: {name}')
    print(f'Verified {len(patches)} patches against pristine source and {len(files)} final files')
    if options.compare_tracked:
        for name in ('linux', 'kernelsu', 'baseband-guard'):
            def content_manifest(path):
                return [{key: value for key, value in entry.items() if key != 'executable'}
                        for entry in tree_manifest(path)]
            acquired = content_manifest(ROOT / '.cache' / name)
            tracked = content_manifest(ROOT / 'kernel-source' / name)
            if acquired != tracked:
                left = {entry['path']: entry for entry in acquired}
                right = {entry['path']: entry for entry in tracked}
                differences = sorted(path for path in left.keys() | right.keys()
                                     if left.get(path) != right.get(path))
                raise RuntimeError(f'{name} source snapshot differs: {differences[:20]}')
            print(f'{name}: {len(acquired)} final entries match tracked content, types and literal symlink targets')


if __name__ == '__main__':
    main()
