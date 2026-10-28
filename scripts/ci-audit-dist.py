#!/usr/bin/env python3
"""Close the CI deliverables after package-sources.sh completed its source audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    version = json.loads((ROOT / 'config/sources.lock.json').read_text())['version']
    archive = DIST / f'ChatGPTKernel-{version}-sources.tar.zst'
    package = DIST / f'ChatGPTKernel-{version}-topaz-tapas-A13-KSU.zip'
    assert archive.is_file() and package.is_file(), 'Missing deliverables'
    # package-sources.sh already compared every archived file, type, mode and
    # literal link target. Bind its mandatory report to this exact archive.
    source_audit = json.loads((DIST / 'source-archive-audit.json').read_text())
    assert source_audit['all_contents_types_modes_and_symlink_targets_match'] is True
    assert source_audit['archive'] == archive.name
    assert source_audit['sha256'] == digest_file(archive)
    with zipfile.ZipFile(package) as output:
        assert output.testzip() is None, 'ZIP CRC mismatch'
        assert output.read('Image') == (ROOT / 'out/arch/arm64/boot/Image').read_bytes()
        assert output.read('ChatGPTKernel.config') == (ROOT / 'out/.config').read_bytes()
    tests = json.loads((ROOT / 'logs/release-tests.json').read_text())
    assert tests['tests_run'] > 0 and not any(tests[name] for name in ('failures', 'errors', 'skips'))
    report = {
        'version': version, 'source_archive': archive.name,
        'source_archive_sha256': digest_file(archive), 'zip': package.name,
        'zip_sha256': digest_file(package), 'release_tests': tests,
        'source_audit_sha256': digest_file(DIST / 'source-archive-audit.json'),
        'all_required_checks_passed': True,
    }
    (DIST / 'ci-dist-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    # CI resource evidence and complete kernel build.log accompany the release.
    for path in sorted((ROOT / 'logs').iterdir()):
        if path.is_file():
            (DIST / ('ci-' + path.name)).write_bytes(path.read_bytes())
    lines = [f'{digest_file(path)}  {path.name}\n' for path in sorted(DIST.iterdir())
             if path.is_file() and path.name != 'SHA256SUMS']
    (DIST / 'SHA256SUMS').write_text(''.join(lines))
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=DIST, check=True)
    sums = {line.split('  ', 1)[1] for line in (DIST / 'SHA256SUMS').read_text().splitlines()}
    assert sums == {path.name for path in DIST.iterdir() if path.is_file() and path.name != 'SHA256SUMS'}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
