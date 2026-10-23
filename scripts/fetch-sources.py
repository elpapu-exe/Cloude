#!/usr/bin/env python3
"""Fetch immutable build inputs. Does not execute remote setup scripts."""
from __future__ import annotations
import json
import subprocess
import tarfile
from pathlib import Path
from fetch_host_tools import download

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'

def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()

def git_source(entry, name, full=False):
    destination = CACHE / name
    if not (destination / '.git').exists():
        destination.mkdir(parents=True, exist_ok=True)
        run('git', 'init', '-q', str(destination))
        run('git', 'remote', 'add', 'origin', entry['repository'], cwd=destination)
        args = ['git', 'fetch', 'origin', entry['commit']]
        if not full:
            args.insert(2, '--depth=1')
        run(*args, cwd=destination)
        run('git', 'checkout', '--detach', entry['commit'], cwd=destination)
    assert run('git', 'rev-parse', 'HEAD', cwd=destination) == entry['commit'], name
    if full:
        if (destination / '.git/shallow').exists():
            run('git', 'fetch', '--unshallow', 'origin', cwd=destination)
        run('git', 'fetch', '--tags', 'origin', cwd=destination)
    return destination

def main():
    CACHE.mkdir(exist_ok=True)
    lock = json.loads((ROOT / 'config/sources.lock.json').read_text())
    git_source(lock['kernel'], 'linux')
    ksu = git_source(lock['kernelsu'], 'kernelsu', full=True)
    assert run('git', 'rev-list', '--count', 'HEAD', cwd=ksu) == '4442'
    assert run('git', 'describe', '--tags', '--abbrev=0', cwd=ksu) == 'v4.2.0-rc1'
    git_source(lock['baseband_guard'], 'baseband-guard', full=True)
    toolchain = lock['toolchain']
    archive = CACHE / toolchain['url'].rsplit('/', 1)[1]
    download(toolchain['url'], archive, toolchain['sha256'])
    if not (CACHE / 'toolchain/bin/clang').exists():
        (CACHE / 'toolchain').mkdir(exist_ok=True)
        with tarfile.open(archive) as package:
            package.extractall(CACHE / 'toolchain', filter='tar')
    for entry in lock['susfs']['reviewed_files']:
        download(entry['url'], CACHE / 'susfs' / entry['path'], entry['sha256'])
    download(lock['installer']['url'], CACHE / 'R10.zip', lock['installer']['sha256'])
    print('All source pins and download checksums verified.')

if __name__ == '__main__':
    main()
