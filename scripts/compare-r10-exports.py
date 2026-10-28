#!/usr/bin/env python3
"""Recover PREL32 exports/absolute CRC tables from R10 and compare candidates.

The layout follows this pinned tree's include/linux/export.h and
include/asm-generic/vmlinux.lds.h. Validate the decoder against the newly built
Image AND its independent vmlinux.symvers before accepting the R10 comparison.
This is not a substitute for testing the phone's actual vendor modules.
"""
from pathlib import Path
import array
import hashlib
import json
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def decode(data):
    assert data[56:60] == b'ARM\x64'
    names = set()
    start = 0
    while True:
        offset = data.find(b'\x00module_layout\x00', start)
        if offset < 0:
            break
        names.add(offset + 1)
        start = offset + 1
    words = array.array('i')
    words.frombytes(data[:len(data) // 4 * 4])
    import sys
    if sys.byteorder != 'little': words.byteswap()
    hits = [i * 4 - 4 for i, value in enumerate(words) if i * 4 + value in names]
    def entry(position):
        if position < 0 or position + 12 > len(data): return None
        _, name_offset, _ = struct.unpack_from('<iii', data, position)
        location = position + 4 + name_offset
        end = data.find(b'\x00', location, location + 200) if 0 <= location < len(data) else -1
        if end < 0: return None
        name = data[location:end]
        if not re.fullmatch(rb'[A-Za-z_][A-Za-z_0-9.]*', name): return None
        return name.decode('ascii')
    results = []
    for hit in hits:
        if entry(hit) != 'module_layout': continue
        lower = upper = hit
        while entry(lower - 12) and entry(lower - 12) < entry(lower): lower -= 12
        while entry(upper + 12) and entry(upper + 12) > entry(upper): upper += 12
        normal = [entry(pos) for pos in range(lower, upper + 1, 12)]
        gpl_start = upper + 12
        if not entry(gpl_start): continue
        gpl_end = gpl_start
        while entry(gpl_end + 12) and entry(gpl_end + 12) > entry(gpl_end): gpl_end += 12
        gpl = [entry(pos) for pos in range(gpl_start, gpl_end + 1, 12)]
        if len(normal) < 1000 or len(gpl) < 1000: continue
        symbols = normal + gpl
        assert len(set(symbols)) == len(symbols)
        crcs = struct.unpack_from('<' + 'I' * len(symbols), data, gpl_end + 12)
        results.append(dict(zip(symbols, crcs)))
    assert len(results) == 1, 'Ambiguous or unsupported export-table layout'
    return results[0]

def main():
    lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
    reference_zip = ROOT / '.cache/R10.zip'
    assert hashlib.sha256(reference_zip.read_bytes()).hexdigest() == lock['installer']['sha256']
    with zipfile.ZipFile(reference_zip) as source: reference = decode(source.read('Image.ksu'))
    candidate = decode((ROOT / 'out/arch/arm64/boot/Image').read_bytes())
    symvers = {}
    for line in (ROOT / 'out/vmlinux.symvers').read_text().splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2] == 'vmlinux': symvers[fields[1]] = int(fields[0], 16)
    assert symvers == candidate, 'Decoder output differs from independent vmlinux.symvers'
    missing = sorted(reference.keys() - candidate.keys())
    changed = {name: {'R10': f'0x{reference[name]:08x}', 'candidate': f'0x{candidate[name]:08x}'}
               for name in sorted(reference.keys() & candidate.keys()) if reference[name] != candidate[name]}
    report = {
        'candidate_image_sha256': hashlib.sha256((ROOT / 'out/arch/arm64/boot/Image').read_bytes()).hexdigest(),
        'reference_exports': len(reference), 'candidate_exports': len(candidate),
        'matching_exports': len(reference.keys() & candidate.keys()) - len(changed),
        'missing_exports': missing, 'changed_crcs': changed,
        'added_exports': sorted(candidate.keys() - reference.keys()),
        'decoder_cross_checked_with_vmlinux_symvers': True,
        'hardware_tested': False, 'phone_vendor_modules_tested': False,
    }
    (ROOT / 'out/abi-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    assert not missing and not changed and not report['added_exports'], 'ABI export comparison failed; do not package a release'

if __name__ == '__main__': main()
