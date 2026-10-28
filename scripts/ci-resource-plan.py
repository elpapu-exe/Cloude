#!/usr/bin/env python3
"""Plan swap against measured free space; provision nothing in this module."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

GIB = 1024 ** 3

def plan_resources(report, *, requested_swap='auto', minimum_disk_gib=45,
                   swap_free_bytes=None, docker_free_bytes=None,
                   swap_shares_workspace=True, swap_shares_docker=True):
    minimum_memory = report['minimum_memory_swap_bytes']
    deficit = max(0, minimum_memory - report['available_memory_swap_bytes'])
    needed = (deficit + GIB - 1) // GIB
    amount = needed if requested_swap == 'auto' else int(requested_swap)
    if amount < 0 or amount < needed:
        raise ValueError('Requested swap cannot meet the configured memory headroom')
    extra = amount * GIB
    cap = report.get('available_swap_capacity_limit_bytes')
    usable_after = report['available_swap_bytes'] + extra
    if cap is not None:
        usable_after = min(usable_after, cap)
    if report['available_ram_bytes'] + usable_after < minimum_memory:
        raise ValueError('The cgroup swap cap prevents meeting the memory headroom')
    disk_minimum = int(minimum_disk_gib * GIB)
    work = report['workspace_free_bytes']
    swap_free = work if swap_free_bytes is None else swap_free_bytes
    docker_free = work if docker_free_bytes is None else docker_free_bytes
    if swap_free < extra + 2 * GIB:
        raise ValueError('Swap filesystem cannot retain a 2 GiB reserve after allocation')
    work_after = work - (extra if swap_shares_workspace else 0)
    docker_after = docker_free - (extra if swap_shares_docker else 0)
    if work_after < disk_minimum or docker_after < 2 * GIB:
        raise ValueError('Measured filesystems cannot retain the configured build and Docker reserves')
    return {'extra_swap_gib': amount, 'extra_swap_bytes': extra,
            'workspace_free_after_swap_bytes': work_after,
            'docker_free_after_swap_bytes': docker_after,
            'minimum_workspace_free_bytes': disk_minimum,
            'minimum_memory_swap_bytes': minimum_memory,
            'interpretation': 'Capacity plan for a monitored attempt; no guarantee of successful linking.'}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--requested-swap', default='auto')
    p.add_argument('--minimum-disk-gib', type=float, default=45)
    p.add_argument('--swap-free-bytes', type=int)
    p.add_argument('--docker-free-bytes', type=int)
    p.add_argument('--swap-separate-workspace', action='store_true')
    p.add_argument('--swap-separate-docker', action='store_true')
    args = p.parse_args()
    report = json.loads(args.report.read_text())
    try:
        result = plan_resources(report, requested_swap=args.requested_swap,
                                minimum_disk_gib=args.minimum_disk_gib,
                                swap_free_bytes=args.swap_free_bytes,
                                docker_free_bytes=args.docker_free_bytes,
                                swap_shares_workspace=not args.swap_separate_workspace,
                                swap_shares_docker=not args.swap_separate_docker)
    except (ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))
