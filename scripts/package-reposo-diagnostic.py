#!/usr/bin/env python3
"""Package the canonical, two-tap suspend collector as a script-only KSU module."""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'modules/chatgpt-reposo-diagnostico'
COLLECTOR = ROOT / 'scripts/chatgpt-suspend-logs.sh'
DIST = ROOT / 'dist/reposo-diagnostic'
VERSION = '0.1.0-rc1'
NAME = 'ChatGPT-Reposo-Diagnostico-' + VERSION
DATE = (2026, 11, 3, 0, 0, 0)
SOURCE_INPUTS = (
    'modules/chatgpt-reposo-diagnostico',
    'scripts/chatgpt-suspend-logs.sh',
    'scripts/package-reposo-diagnostic.py',
    'scripts/publish-reposo-diagnostic.sh',
    'tests/test_suspend_diagnostic.py',
    '.github/workflows/reposo-diagnostic.yml',
)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_zip(target, files):
    """Use one byte source per member, then audit names, bytes, modes and CRC."""
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, path in sorted(files.items()):
            assert path.is_file() and not path.is_symlink(), name
            entry = zipfile.ZipInfo(name, DATE)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as check:
        assert check.testzip() is None, 'ZIP CRC failure'
        assert len(check.namelist()) == len(files) and set(check.namelist()) == set(files)
        for name, path in files.items():
            assert check.read(name) == path.read_bytes(), name
            expected = stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)
            assert check.getinfo(name).external_attr >> 16 == expected, name


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    expected = {NAME + '-KSU.zip', NAME + '-sources.zip', 'build-manifest.json', 'tests.log', 'SHA256SUMS'}
    assert all(p.name in expected and p.is_file() for p in DIST.iterdir()), 'Unexpected output; use a separate clean output directory'
    module_files = {p.relative_to(PROJECT).as_posix(): p for p in PROJECT.rglob('*') if p.is_file()}
    required = {'module.prop', 'skip_mount', 'customize.sh', 'action.sh', 'INSTRUCCIONES.txt', 'LICENSE', 'README.md'}
    assert set(module_files) == required, 'Missing or unexpected module file; no boot/service hooks are allowed'
    assert COLLECTOR.is_file() and not COLLECTOR.is_symlink(), 'Canonical collector missing'
    assert (ROOT / 'tests/test_suspend_diagnostic.py').is_file(), 'Required collector test missing'
    props = dict(line.split('=', 1) for line in module_files['module.prop'].read_text().splitlines())
    assert props['id'] == 'chatgpt_reposo_diagnostico' and props['version'] == 'v' + VERSION
    assert props['versionCode'] == '1' and props['name'] == 'ChatGPT Reposo Diagnóstico'
    for path in (*PROJECT.glob('*.sh'), COLLECTOR):
        subprocess.run(['sh', '-n', str(path)], check=True)
    test = subprocess.run([
        sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
        '-p', 'test_suspend_diagnostic.py', '-v',
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (DIST / 'tests.log').write_text(test.stdout)
    assert test.returncode == 0 and 'skipped=' not in test.stdout, 'Diagnostic regression failed or skipped'
    match = re.search(r'^Ran (\d+) tests?\b', test.stdout, re.MULTILINE)
    assert match and int(match.group(1)) > 0, 'Required collector suite is empty'
    test_count = int(match.group(1))
    install_files = {**module_files, 'bin/collect.sh': COLLECTOR}
    write_zip(DIST / (NAME + '-KSU.zip'), install_files)
    with zipfile.ZipFile(DIST / (NAME + '-KSU.zip')) as package:
        assert package.read('bin/collect.sh') == COLLECTOR.read_bytes()
        assert 'service.sh' not in package.namelist() and 'post-fs-data.sh' not in package.namelist()
    source_files = {path.relative_to(ROOT).as_posix(): path for path in module_files.values()}
    for name in SOURCE_INPUTS[1:]:
        source_files[name] = ROOT / name
    write_zip(DIST / (NAME + '-sources.zip'), source_files)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output([
        'git', 'status', '--porcelain', '--', *SOURCE_INPUTS,
    ], cwd=ROOT, text=True).strip())
    if os.environ.get('CI') == 'true':
        assert not dirty, 'CI sources differ from the checked-out commit'
    manifest = {
        'project': 'ChatGPT Reposo Diagnóstico', 'module_id': props['id'], 'version': VERSION,
        'source_commit': commit, 'worktree_dirty': dirty,
        'tests_run': test_count, 'failures': 0, 'errors': 0, 'skips': 0,
        'hardware_tested': False, 'kernel_build_performed': False,
        'runtime': {'invocation': 'bin/collect.sh auto', 'daemon': False,
                    'boot_scripts': False, 'timer': False, 'wakelock': False,
                    'device_tunable_writes': False, 'network_upload': False,
                    'private_state_directory': '/data/adb/chatgpt-reposo-diagnostico',
                    'report_directory': '/sdcard/Download'},
        'collector': {'canonical_source': COLLECTOR.relative_to(ROOT).as_posix(),
                      'installed_path': 'bin/collect.sh', 'sha256': sha(COLLECTOR),
                      'identical_bytes_verified': True},
        'zip_audit': {'crc': True, 'closed_member_list': True, 'file_bytes': True, 'modes': True},
        'sources': {name: sha(path) for name, path in sorted(source_files.items())},
        'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(DIST.glob('*.zip'))},
    }
    (DIST / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (DIST / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(DIST.iterdir()) if p.name != 'SHA256SUMS'))
    assert {p.name for p in DIST.iterdir()} == expected
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=DIST, check=True)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
