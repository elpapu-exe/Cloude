#!/usr/bin/env python3
"""Replay the full patch series against pristine tracked files and compare it."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/linux'
patches = sorted((ROOT / 'patches').glob('*.patch'))
files = set()
for patch in patches:
    for line in patch.read_text().splitlines():
        if line.startswith('--- a/'):
            files.add(line[6:])
with tempfile.TemporaryDirectory() as directory:
    check = Path(directory)
    for name in files:
        target = check / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(['git', 'show', f'HEAD:{name}'], cwd=SOURCE))
    for patch in patches:
        subprocess.run(['patch', '--fuzz=0', '-p1', '-i', str(patch)], cwd=check, check=True, stdout=subprocess.DEVNULL)
    for name in files:
        assert (check / name).read_bytes() == (SOURCE / name).read_bytes(), f'Unrecorded source edit: {name}'
print(f'Verified {len(patches)} patches against pristine source and {len(files)} final files')
