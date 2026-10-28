#!/usr/bin/env python3
"""Static release validation; does not claim hardware or vendor-module testing."""
from pathlib import Path
import gzip
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
subprocess.run(['python3', str(ROOT / 'scripts/verify-config.py')], check=True)
subprocess.run(['python3', str(ROOT / 'scripts/check-patches.py')], check=True)
image = (OUT / 'arch/arm64/boot/Image').read_bytes()
assert image[56:60] == b'ARM\x64', 'Invalid ARM64 Image header'
with (OUT / 'vmlinux').open('rb') as source:
    assert source.read(6) == b'\x7fELF\x02\x01', 'Invalid ELF64 vmlinux'
    source.seek(18)
    assert int.from_bytes(source.read(2), 'little') == 183, 'Not AArch64'
release = (OUT / 'include/config/kernel.release').read_text().strip()
assert release == '5.15.216-ChatGPTKernel-0.1.0-rc4', release
assert release.encode() in image, 'Release string absent from image'
assert b'v4.2.0-rc1-7e92d45e@ReSukiSU' in image, 'Unexpected KSU identity'
assert b'v2.3.0' in image, 'SUSFS identity absent'
assert b'a54e0dc6' in image, 'BBG identity absent'
start = image.index(b'IKCFG_ST') + 8
end = image.index(b'IKCFG_ED', start)
embedded = gzip.decompress(image[start:end])
assert embedded == (OUT / '.config').read_bytes(), 'Embedded configuration differs from actual build'
assert 'module_layout' in (OUT / 'vmlinux.symvers').read_text(), 'Module CRC data absent'
# Read the file-backed ELF symbol rather than trusting source or a log message.
import struct
import mmap
elf_file = (OUT / 'vmlinux').open('rb')
elf = mmap.mmap(elf_file.fileno(), 0, access=mmap.ACCESS_READ)
shoff = struct.unpack_from('<Q', elf, 40)[0]
shentsize, shnum = struct.unpack_from('<HH', elf, 58)
sections = [struct.unpack_from('<IIQQQQIIQQ', elf, shoff + i * shentsize) for i in range(shnum)]
found = []
for section in sections:
    if section[1] != 2:  # SHT_SYMTAB
        continue
    strings = sections[section[6]]
    strtab = elf[strings[4]:strings[4] + strings[5]]
    for offset in range(section[4], section[4] + section[5], section[9]):
        name, info, other, index, value, size = struct.unpack_from('<IBBHQQ', elf, offset)
        if strtab[name:strtab.find(b'\0', name)] != b'watermark_scale_factor':
            continue
        data = sections[index]
        assert data[1] == 1 and size == 4, 'Unexpected watermark symbol storage'
        address = data[4] + value - data[3]
        found.append(struct.unpack_from('<i', elf, address)[0])
assert found == [10], f'Unexpected compiled reclaim headroom initializer: {found}'
manifest = {
    'project': 'ChatGPT Kernel', 'version': '0.1.0-rc4',
    'release': release, 'reconstruction': 'rc4 successor of published rc3-rebuild1; newly built binary',
    'project_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'image_bytes': len(image),
    'image_sha256': hashlib.sha256(image).hexdigest(),
    'config_sha256': hashlib.sha256(embedded).hexdigest(),
    'vmlinux_symvers_sha256': hashlib.sha256((OUT / 'vmlinux.symvers').read_bytes()).hexdigest(),
    'patches': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'patches').glob('*.patch'))},
    'host_tools_lock_sha256': hashlib.sha256((ROOT / 'config/host-tools.lock.json').read_bytes()).hexdigest(),
    'source_pins': json.loads((ROOT / 'config/sources.lock.json').read_text()),
    'validation': {'compiled': True, 'arm64_header': True, 'actual_ikconfig': True,
                   'hardware_boot': False, 'vendor_module_crc_match': 'not tested against phone modules',
                   'performance': 'not measured on hardware',
                   'btf_unresolved_functions': sorted(set(re.findall(
                       r'WARN: resolve_btfids: unresolved symbol (\w+)',
                       (ROOT / 'logs/build.log').read_text() if (ROOT / 'logs/build.log').exists() else '')))},
}
(OUT / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({key: manifest[key] for key in ('release', 'image_bytes', 'image_sha256')}))
