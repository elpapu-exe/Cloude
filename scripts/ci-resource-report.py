#!/usr/bin/env python3
"""Record host/cgroup resources; fail before Full LTO when headroom is inadequate."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import time

GIB = 1024 ** 3
ROOT = Path(__file__).resolve().parents[1]


def bounded_available(directory: Path, maximum: str, current: str):
    try:
        limit = (directory / maximum).read_text().strip()
        used = int((directory / current).read_text())
        return None if limit == 'max' else max(0, int(limit) - used)
    except (OSError, ValueError):
        return None


def resource_report():
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        memory[key] = int(value.split()[0]) * 1024
    available_ram = memory['MemAvailable']
    available_swap = memory['SwapFree']
    cgroup_records = []
    unified = next((line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines()
                    if line.startswith('0::')), None)
    if unified is not None:
        base = Path('/sys/fs/cgroup')
        directory = base / unified.lstrip('/')
        # A namespaced container can expose / as the current cgroup instead.
        if not directory.exists():
            directory = base
        for ancestor in (directory, *directory.parents):
            if ancestor != base and base not in ancestor.parents:
                break
            ram = bounded_available(ancestor, 'memory.max', 'memory.current')
            swap = bounded_available(ancestor, 'memory.swap.max', 'memory.swap.current')
            if ram is not None:
                available_ram = min(available_ram, ram)
            if swap is not None:
                available_swap = min(available_swap, swap)
            if ram is not None or swap is not None:
                cgroup_records.append({'path': str(ancestor), 'available_ram_bytes': ram,
                                       'available_swap_bytes': swap})
            if ancestor == base:
                break
    else:
        # Older cgroup-v1 runners: include memory and combined memory+swap caps.
        for base in (Path('/sys/fs/cgroup/memory'),):
            if not base.is_dir():
                continue
            relative = next((line.split(':', 2)[2] for line in
                             Path('/proc/self/cgroup').read_text().splitlines()
                             if 'memory' in line.split(':', 2)[1].split(',')), '/')
            directory = base / relative.lstrip('/')
            for ancestor in (directory, *directory.parents):
                if ancestor != base and base not in ancestor.parents:
                    break
                ram = bounded_available(ancestor, 'memory.limit_in_bytes', 'memory.usage_in_bytes')
                total = bounded_available(ancestor, 'memory.memsw.limit_in_bytes', 'memory.memsw.usage_in_bytes')
                if ram is not None:
                    available_ram = min(available_ram, ram)
                if total is not None:
                    available_swap = min(available_swap, max(0, total - available_ram))
                cgroup_records.append({'path': str(ancestor), 'available_ram_bytes': ram,
                                       'available_memory_swap_bytes': total})
                if ancestor == base:
                    break
    return {
        'observed_at_epoch': int(time.time()), 'cpu_count': os.cpu_count(),
        'host_mem_total_bytes': memory['MemTotal'], 'host_swap_total_bytes': memory['SwapTotal'],
        'available_ram_bytes': available_ram, 'available_swap_bytes': available_swap,
        'available_memory_swap_bytes': available_ram + available_swap,
        'workspace_free_bytes': shutil.disk_usage(ROOT).free,
        'cgroup_limits': cgroup_records,
        'minimum_memory_swap_bytes': 36 * GIB, 'minimum_workspace_free_bytes': 45 * GIB,
        'interpretation': 'Capacity preflight only; swap can be slow and successful linking is not guaranteed.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enforce', action='store_true')
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    report = resource_report()
    text = json.dumps(report, indent=2) + '\n'
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(text)
    print(text, end='')
    if options.enforce:
        if report['available_memory_swap_bytes'] < report['minimum_memory_swap_bytes']:
            raise SystemExit('Full LTO requires at least 36 GiB available RAM + usable swap; choose a larger runner or provision swap.')
        if report['workspace_free_bytes'] < report['minimum_workspace_free_bytes']:
            raise SystemExit('Full LTO requires at least 45 GiB workspace space after provisioning swap; choose a larger runner.')
