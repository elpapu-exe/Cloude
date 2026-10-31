#!/usr/bin/env python3
"""Build a small script-only KernelSU module; no kernel or phone is modified."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'modules/chatgpt-fluidez-memoria'
DIST = ROOT / 'dist/fluidez-module'
VERSION = '0.1.0-rc1'
NAME = 'ChatGPT-Fluidez-Memoria-' + VERSION
DATE = (2026, 10, 31, 0, 0, 0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_zip(target, files):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, path in sorted(files.items()):
            entry = zipfile.ZipInfo(name, DATE)
            entry.create_system = 3
            entry.external_attr = (0o100000 | (0o755 if path.suffix == '.sh' else 0o644)) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as check:
        assert check.testzip() is None
        assert set(check.namelist()) == set(files)
        for name, path in files.items():
            assert check.read(name) == path.read_bytes()


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    # Refuse stale deliverables instead of silently hashing unrelated files.
    expected = {NAME + '-KSU.zip', NAME + '-sources.zip', 'build-manifest.json', 'tests.log', 'SHA256SUMS'}
    assert all(p.name in expected and p.is_file() for p in DIST.iterdir()), 'Unexpected output; use a separate clean output directory'
    files = {str(p.relative_to(PROJECT)): p for p in PROJECT.rglob('*') if p.is_file()}
    required = {'module.prop', 'skip_mount', 'customize.sh', 'service.sh', 'action.sh', 'uninstall.sh', 'bin/control.sh', 'INSTRUCCIONES.txt', 'LICENSE', 'README.md'}
    assert set(files) == required, 'Missing or unexpected module files'
    props = dict(line.split('=', 1) for line in files['module.prop'].read_text().splitlines())
    assert props['id'] == 'chatgpt_fluidez_memoria' and props['version'] == 'v' + VERSION
    for path in PROJECT.rglob('*.sh'):
        subprocess.run(['sh', '-n', str(path)], check=True)
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_fluidez_module.py', '-v'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (DIST / 'tests.log').write_text(test.stdout)
    assert test.returncode == 0 and 'skipped=' not in test.stdout, 'Module regression failed or skipped'
    write_zip(DIST / (NAME + '-KSU.zip'), files)
    source_files = {str(p.relative_to(ROOT)): p for p in files.values()}
    for relative in ('scripts/package-fluidez-module.py', 'scripts/publish-fluidez-module.sh', 'tests/test_fluidez_module.py', '.github/workflows/fluidez-module.yml'):
        source_files[relative] = ROOT / relative
    write_zip(DIST / (NAME + '-sources.zip'), source_files)
    tests_run = next(line for line in test.stdout.splitlines() if line.startswith('Ran '))
    test_count = int(re.search(r'Ran (\d+) tests?', tests_run).group(1))
    assert test_count > 0, 'Required module test suite is empty'
    manifest = {'project': 'ChatGPT Fluidez Memoria', 'version': VERSION,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'worktree_dirty': bool(subprocess.check_output(['git','status','--porcelain','--','modules/chatgpt-fluidez-memoria','scripts/package-fluidez-module.py','scripts/publish-fluidez-module.sh','tests/test_fluidez_module.py','.github/workflows/fluidez-module.yml'], cwd=ROOT, text=True).strip()),
                'tests': tests_run, 'tests_run': test_count, 'skips': 0,
                'hardware_tested': False, 'performance_measured': False,
                'parameters': {'mglru': 'current | 1 only when bit0 is disabled', 'watermark_scale_factor': 'raise to 64 only when current is lower'},
                'sources': {name: sha(path) for name, path in sorted(source_files.items())},
                'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(DIST.glob('*.zip'))}}
    (DIST / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (DIST / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(DIST.iterdir()) if p.name != 'SHA256SUMS'))
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=DIST, check=True)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
