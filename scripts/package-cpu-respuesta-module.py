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
PROJECT = ROOT / 'modules/chatgpt-cpu-respuesta'
DIST = ROOT / 'dist/cpu-respuesta-module'
VERSION = '0.1.0-rc1'
NAME = 'ChatGPT-CPU-Respuesta-' + VERSION
DATE = (2026, 11, 1, 0, 0, 0)


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
    required = {'module.prop', 'skip_mount', 'customize.sh', 'service.sh', 'action.sh', 'uninstall.sh', 'bin/control.sh', 'bin/collect.sh', 'INSTRUCCIONES.txt', 'LICENSE', 'README.md'}
    assert set(files) == required, 'Missing or unexpected module files'
    props = dict(line.split('=', 1) for line in files['module.prop'].read_text().splitlines())
    assert props['id'] == 'chatgpt_cpu_respuesta' and props['version'] == 'v' + VERSION
    for path in PROJECT.rglob('*.sh'):
        subprocess.run(['sh', '-n', str(path)], check=True)
    assert files['bin/collect.sh'].read_bytes() == (ROOT / 'scripts/chatgpt-kernel-logs.sh').read_bytes(), 'Bundled diagnostic differs from the audited collector'
    test_log = ''
    test_count = 0
    suites = {}
    for pattern in ('test_cpu_respuesta_module.py', 'test_diagnostic.py', 'test_diagnostic_runtime_details.py'):
        test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        test_log += '\n=== ' + pattern + ' ===\n' + test.stdout
        (DIST / 'tests.log').write_text(test_log)
        assert test.returncode == 0 and 'skipped=' not in test.stdout, 'Required regression failed or skipped: ' + pattern
        count = int(re.search(r'Ran (\d+) tests?', test.stdout).group(1))
        assert count > 0, 'Required test suite is empty: ' + pattern
        suites[pattern] = count
        test_count += count
    write_zip(DIST / (NAME + '-KSU.zip'), files)
    source_files = {str(p.relative_to(ROOT)): p for p in files.values()}
    for relative in ('scripts/package-cpu-respuesta-module.py', 'scripts/publish-cpu-respuesta-module.sh', 'tests/test_cpu_respuesta_module.py', 'tests/test_fluidez_module.py', 'tests/test_diagnostic.py', 'tests/test_diagnostic_runtime_details.py', 'scripts/chatgpt-kernel-logs.sh', '.github/workflows/cpu-respuesta-module.yml'):
        source_files[relative] = ROOT / relative
    write_zip(DIST / (NAME + '-sources.zip'), source_files)
    manifest = {'project': 'ChatGPT CPU Respuesta', 'version': VERSION,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'worktree_dirty': bool(subprocess.check_output(['git','status','--porcelain','--','modules/chatgpt-cpu-respuesta','scripts/package-cpu-respuesta-module.py','scripts/publish-cpu-respuesta-module.sh','tests/test_cpu_respuesta_module.py','tests/test_fluidez_module.py','tests/test_diagnostic.py','tests/test_diagnostic_runtime_details.py','scripts/chatgpt-kernel-logs.sh','.github/workflows/cpu-respuesta-module.yml'], cwd=ROOT, text=True).strip()),
                'tests_run': test_count, 'suites': suites, 'skips': 0,
                'hardware_tested': False, 'performance_measured': False,
                'parameters': {'walt.up_rate_limit_us': 'if20001..100000us, ceil(0.75 * original), only on unambiguous active WALT controls', 'gpu': 'read-only diagnostic; no tuning', 'zram': 'unchanged; SmartPack remains controller'},
                'sources': {name: sha(path) for name, path in sorted(source_files.items())},
                'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(DIST.glob('*.zip'))}}
    (DIST / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (DIST / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(DIST.iterdir()) if p.name != 'SHA256SUMS'))
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=DIST, check=True)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
