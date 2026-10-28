#!/usr/bin/env python3
"""Acquire pinned inputs with verified archive fallback and honest provenance."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from fetch_host_tools import download
from source_archive import extract_source, tree_digest, write_receipt

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True,
                                   stderr=subprocess.PIPE, timeout=300).strip()


def verify_git(entry, destination, full=False):
    if run('git', 'rev-parse', 'HEAD', cwd=destination) != entry['commit']:
        raise RuntimeError(f'Wrong source commit: {destination.name}')
    if run('git', 'status', '--porcelain', cwd=destination):
        raise RuntimeError(f'Source is not pristine: {destination.name}')
    details = {'method': 'git', 'commit': entry['commit'], 'repository': entry['repository']}
    if full:
        if (destination / '.git/shallow').exists():
            raise RuntimeError(f'Full Git history required: {destination.name}')
        count = int(run('git', 'rev-list', '--count', 'HEAD', cwd=destination))
        details['commit_count'] = count
        if 'commit_count' in entry and count != entry['commit_count']:
            raise RuntimeError('Pinned commit count differs from real Git history')
        if 'nearest_tag' in entry:
            tag = run('git', 'describe', '--tags', '--abbrev=0', cwd=destination)
            if tag != entry['nearest_tag']:
                raise RuntimeError('Pinned nearest tag differs from real Git history')
            details['nearest_tag'] = tag
    return details


def acquire_source(entry, name, full=False, *, cache=None, prefer_archive=False):
    cache = CACHE if cache is None else Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / name
    receipt_path = cache / 'source-receipts' / (name + '.json')
    if destination.exists():
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt['commit'] != entry['commit']:
                raise RuntimeError('Existing receipt has a different source commit')
            expected_tree = receipt['tree_sha256']
            if name == 'linux' and (cache / 'prepared.json').exists():
                expected_tree = json.loads((cache / 'prepared.json').read_text())['prepared_tree_sha256']
            if tree_digest(destination) != expected_tree:
                raise RuntimeError('Existing source changed after acquisition')
            return destination
        # Adopt only a demonstrably pristine real Git checkout. Never infer
        # provenance from a directory name or create synthetic Git metadata.
        details = verify_git(entry, destination, full)
    else:
        failure = None
        with tempfile.TemporaryDirectory(prefix='.' + name + '-fetch-', dir=cache) as tmp:
            staging = Path(tmp) / 'source'
            if not prefer_archive:
                try:
                    run('git', 'init', '-q', str(staging))
                    run('git', 'remote', 'add', 'origin', entry['repository'], cwd=staging)
                    args = ['git', 'fetch', 'origin', entry['commit']]
                    if not full:
                        args.insert(2, '--depth=1')
                    run(*args, cwd=staging)
                    run('git', 'checkout', '--detach', entry['commit'], cwd=staging)
                    if full:
                        run('git', 'fetch', '--tags', 'origin', cwd=staging)
                    details = verify_git(entry, staging, full)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                    failure = type(error).__name__
                    shutil.rmtree(staging, ignore_errors=True)
            if prefer_archive or failure:
                url, digest = entry.get('archive_url'), entry.get('archive_sha256')
                if not url or not digest or entry['commit'] not in url:
                    raise RuntimeError(f'Git acquisition failed for {name}; no immutable archive pin')
                archive = cache / 'source-archives' / f'{name}-{entry["commit"]}.tar.gz'
                download(url, archive, digest)
                extract_source(archive, staging, entry['commit'], digest)
                details = {'method': 'immutable-archive', 'commit': entry['commit'],
                           'repository': entry['repository'], 'archive_url': url,
                           'archive_sha256': digest, 'archive_bytes': archive.stat().st_size,
                           'git_history_present': False, 'git_failure_class': failure}
            staging.rename(destination)
    details['tree_sha256'] = tree_digest(destination)
    write_receipt(receipt_path, details)
    print(f'{name}: verified {details["method"]} at {entry["commit"]}', flush=True)
    return destination


def main():
    CACHE.mkdir(exist_ok=True)
    lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
    method = os.environ.get('CHATGPT_SOURCE_METHOD', 'git')
    if method not in ('git', 'archive'):
        raise SystemExit('CHATGPT_SOURCE_METHOD must be git or archive')
    archive = method == 'archive'
    acquire_source(lock['kernel'], 'linux', prefer_archive=archive)
    acquire_source(lock['kernelsu'], 'kernelsu', full=True, prefer_archive=archive)
    acquire_source(lock['baseband_guard'], 'baseband-guard', full=True, prefer_archive=archive)
    toolchain = lock['toolchain']
    package_path = CACHE / toolchain['url'].rsplit('/', 1)[1]
    download(toolchain['url'], package_path, toolchain['sha256'])
    if not (CACHE / 'toolchain/bin/clang').exists():
        staging = Path(tempfile.mkdtemp(prefix='.toolchain-', dir=CACHE))
        try:
            with tarfile.open(package_path) as package:
                package.extractall(staging, filter='data')
            staging.rename(CACHE / 'toolchain')
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    for entry in lock['susfs']['reviewed_files']:
        download(entry['url'], CACHE / 'susfs' / entry['path'], entry['sha256'])
    download(lock['installer']['url'], CACHE / 'R10.zip', lock['installer']['sha256'])
    print('Source provenance and pinned input checksums verified.')


if __name__ == '__main__':
    main()
