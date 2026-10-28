#!/usr/bin/env python3
"""Run one CI build phase and stop its process group if disk reserve is exhausted."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024 ** 3

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True)
    parser.add_argument('--minimum-free-gib', type=float, default=2)
    parser.add_argument('--log', type=Path, default=ROOT / 'logs/disk-guard.jsonl')
    parser.add_argument('--poll-seconds', type=float, default=2)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.minimum_free_gib <= 0 or args.poll_seconds <= 0:
        parser.error('a command and positive reserve/poll values are required')
    args.log.parent.mkdir(parents=True, exist_ok=True)
    reserve = int(args.minimum_free_gib * GIB)
    child = None

    def sample(event):
        paths = {str(path): shutil.disk_usage(path).free for path in (ROOT, Path('/'))}
        outputs = {}
        for pattern in ('vmlinux', 'vmlinux.o', '.tmp_vmlinux*', '.btf.*'):
            for path in (ROOT / 'out').glob(pattern):
                try:
                    if path.is_file():
                        outputs[path.name] = path.stat().st_size
                except FileNotFoundError:
                    pass  # The linker atomically replaces temporary outputs.
        report = {'epoch': int(time.time()), 'phase': args.phase, 'event': event,
                  'free_bytes': paths, 'minimum_free_bytes': reserve,
                  'link_output_sizes': outputs}
        with args.log.open('a') as stream:
            stream.write(json.dumps(report, separators=(',', ':')) + '\n')
        return min(paths.values()) >= reserve

    def stop_group():
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()

    def interrupted(signum, frame):
        stop_group()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    if not sample('before'):
        print('Disk reserve is insufficient; phase was not started.', file=sys.stderr)
        return 125
    try:
        child = subprocess.Popen(command, start_new_session=True)
        while True:
            try:
                status = child.wait(timeout=args.poll_seconds)
                sample('finished')
                return status if status >= 0 else 128 - status
            except subprocess.TimeoutExpired:
                if not sample('running'):
                    print('Disk reserve crossed the safety threshold; stopping this build phase.', file=sys.stderr)
                    stop_group()
                    sample('stopped-low-disk')
                    return 125
    finally:
        stop_group()

if __name__ == '__main__':
    sys.exit(main())
