#!/usr/bin/env python3
"""Apply the recorded patches to verified pristine sources exactly once."""
from pathlib import Path
import json
import shutil
import subprocess
from source_archive import sha256, tree_digest, write_receipt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/linux'


def main():
    receipt = ROOT / '.cache/prepared.json'
    if receipt.exists():
        raise SystemExit('Already prepared; retain this tree or use a separate clean checkout.')
    lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
    provenance = json.loads((ROOT / '.cache/source-receipts/linux.json').read_text())
    if provenance['commit'] != lock['kernel']['commit'] or tree_digest(SOURCE) != provenance['tree_sha256']:
        raise SystemExit('Kernel source no longer matches verified acquisition receipt')
    # Upstream ReSukiSU derives its numeric identity from real Git history.
    # Archive acquisition is supported for audit/storage, but we fail clearly
    # instead of inventing a .git directory or silently changing its identity.
    ksu = ROOT / '.cache/kernelsu'
    if not (ksu / '.git').exists() or (ksu / '.git/shallow').exists():
        raise SystemExit('KSU build needs its complete pinned Git history; archive-only KSU is not buildable with this Kbuild')
    for name, key in (('kernelsu', 'kernelsu'), ('baseband-guard', 'baseband_guard')):
        acquired = json.loads((ROOT / '.cache/source-receipts' / (name + '.json')).read_text())
        if acquired['commit'] != lock[key]['commit'] or tree_digest(ROOT / '.cache' / name) != acquired['tree_sha256']:
            raise SystemExit(f'{name} no longer matches verified acquisition receipt')
    patches = sorted((ROOT / 'patches').glob('*.patch'))
    for patch in patches:
        command = ['patch', '--no-backup-if-mismatch', '--fuzz=0', '-p1', '-i', str(patch)]
        subprocess.run(command[:1] + ['--dry-run'] + command[1:], cwd=SOURCE, check=True)
        subprocess.run(command, cwd=SOURCE, check=True)
    for relative in ('fs/susfs.c', 'include/linux/susfs.h', 'include/linux/susfs_def.h'):
        src = ROOT / '.cache/susfs/kernel_patches' / relative
        entry = next(e for e in lock['susfs']['reviewed_files'] if e['path'] == 'kernel_patches/' + relative)
        if sha256(src) != entry['sha256']:
            raise RuntimeError(f'SUSFS checksum mismatch: {relative}')
        shutil.copyfile(src, SOURCE / relative)
    (SOURCE / 'drivers/kernelsu').symlink_to('../../kernelsu/kernel')
    (SOURCE / 'security/baseband-guard').symlink_to('../../baseband-guard')
    if (SOURCE / '.git').exists():
        subprocess.run(['git', 'diff', '--check'], cwd=SOURCE, check=True)
    write_receipt(receipt, {'kernel_commit': provenance['commit'], 'prepared': True,
                           'acquisition': provenance,
                           'patches': {p.name: sha256(p) for p in patches},
                           'prepared_tree_sha256': tree_digest(SOURCE)})


if __name__ == '__main__':
    main()
