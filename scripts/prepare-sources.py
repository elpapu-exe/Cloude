#!/usr/bin/env python3
"""Apply the audited patches to a clean pinned kernel source tree once."""
from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/linux'
receipt = ROOT / '.cache/prepared.json'
lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
assert head == lock['kernel']['commit']
if receipt.exists():
    raise SystemExit('Already prepared; retain this tree or use a separate clean checkout.')
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE), 'Source must be clean'
for patch in sorted((ROOT / 'patches').glob('*.patch')):
    command = ['patch', '--no-backup-if-mismatch', '--fuzz=0', '-p1', '-i', str(patch)]
    subprocess.run(command[:1] + ['--dry-run'] + command[1:], cwd=SOURCE, check=True)
    subprocess.run(command, cwd=SOURCE, check=True)
for relative in ('fs/susfs.c', 'include/linux/susfs.h', 'include/linux/susfs_def.h'):
    shutil.copyfile(ROOT / '.cache/susfs/kernel_patches' / relative, SOURCE / relative)
(SOURCE / 'drivers/kernelsu').symlink_to('../../kernelsu/kernel')
(SOURCE / 'security/baseband-guard').symlink_to('../../baseband-guard')
subprocess.run(['git', 'diff', '--check'], cwd=SOURCE, check=True)
receipt.write_text(json.dumps({'kernel_commit': head, 'prepared': True}, indent=2) + '\n')
