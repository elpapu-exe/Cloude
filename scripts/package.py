#!/usr/bin/env python3
"""Package a validated, freshly compiled image; no publication or flashing."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
subprocess.run(['python3', str(ROOT / 'scripts/verify-artifact.py')], check=True)
subprocess.run(['python3', str(ROOT / 'scripts/compare-r10-exports.py')], check=True)
subprocess.run(['python3', str(ROOT / 'tests/test_backup.py')], check=True)
lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
reference = ROOT / '.cache/R10.zip'
assert hashlib.sha256(reference.read_bytes()).hexdigest() == lock['installer']['sha256']
name = 'ChatGPTKernel-0.1.0-rc1-topaz-tapas-A13-KSU'
package = DIST / (name + '.zip')
members = {}
with zipfile.ZipFile(reference) as source:
    for entry in source.infolist():
        if entry.is_dir():
            continue
        if entry.filename == 'LICENSE' or entry.filename.startswith(('tools/', 'META-INF/')):
            members[entry.filename] = (source.read(entry), 0o755 if entry.filename.startswith(('tools/', 'META-INF/')) else 0o644)
members.update({
    'anykernel.sh': ((ROOT / 'installer/anykernel.sh').read_bytes(), 0o755),
    'tools/chatgpt-backup.sh': ((ROOT / 'installer/chatgpt-backup.sh').read_bytes(), 0o755),
    'Image': ((ROOT / 'out/arch/arm64/boot/Image').read_bytes(), 0o644),
    'ChatGPTKernel.config': ((ROOT / 'out/.config').read_bytes(), 0o644),
    'build-manifest.json': ((ROOT / 'out/build-manifest.json').read_bytes(), 0o644),
    'abi-comparison.json': ((ROOT / 'out/abi-comparison.json').read_bytes(), 0o644),
    'README.md': ((ROOT / 'docs/installation.md').read_bytes(), 0o644),
})
with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
    for path, (data, mode) in sorted(members.items()):
        info = zipfile.ZipInfo(path, date_time=(2026, 10, 23, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (0o100000 | mode) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        output.writestr(info, data)
with zipfile.ZipFile(package) as output:
    assert output.testzip() is None
    assert output.read('Image') == members['Image'][0]
    forbidden = ('dtb', 'dtbo.img', 'vendor_boot.img', 'init_boot.img', 'Image.noksu', 'Image.ksu')
    assert not set(forbidden).intersection(output.namelist())
    assert not any(p.endswith('.ko') for p in output.namelist())
for source, target in (
    ('out/build-manifest.json', 'build-manifest.json'),
    ('out/.config', 'ChatGPTKernel.config'),
    ('docs/installation.md', 'LEEME-instalacion.md'),
    ('out/Module.symvers', 'Module.symvers'),
    ('out/abi-comparison.json', 'abi-comparison.json'),
):
    (DIST / target).write_bytes((ROOT / source).read_bytes())
checksums = []
for path in sorted(DIST.iterdir()):
    if path.is_file() and path.name != 'SHA256SUMS':
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        checksums.append(f'{digest}  {path.name}\n')
(DIST / 'SHA256SUMS').write_text(''.join(checksums))
print(f'Created {package} ({package.stat().st_size} bytes)')
