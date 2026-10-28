#!/usr/bin/env python3
"""Capacity arithmetic and real child-process disk guard failure paths."""
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLAN = runpy.run_path(str(ROOT / 'scripts/ci-resource-plan.py'))['plan_resources']
GUARD = runpy.run_path(str(ROOT / 'scripts/ci-guard-space.py'))['main']
GIB = 1024 ** 3


def capacity(work=43, ram=6.5, swap=3, cap=None):
    return {'minimum_memory_swap_bytes': 36 * GIB,
            'available_ram_bytes': int(ram * GIB),
            'available_swap_bytes': int(swap * GIB),
            'available_memory_swap_bytes': int((ram + swap) * GIB),
            'available_swap_capacity_limit_bytes': cap,
            'workspace_free_bytes': int(work * GIB)}


class ResourceTests(unittest.TestCase):
    def test_auto_swap_rounds_deficit_and_preserves_workspace(self):
        result = PLAN(capacity(), minimum_disk_gib=15)
        self.assertEqual(result['extra_swap_gib'], 28)
        self.assertEqual(result['workspace_free_after_swap_bytes'], 15 * GIB)

    def test_fixed_swap_cannot_consume_build_reserve(self):
        with self.assertRaises(ValueError):
            PLAN(capacity(), requested_swap='32', minimum_disk_gib=15)

    def test_memory_deficit_and_cgroup_cap_reject_before_provision(self):
        for request, cap in [('0', None), ('26', None), ('auto', 16 * GIB)]:
            with self.subTest(request=request, cap=cap), self.assertRaises(ValueError):
                PLAN(capacity(cap=cap), requested_swap=request, minimum_disk_gib=15)

    def test_large_physical_runner_needs_no_additional_swap(self):
        result = PLAN(capacity(work=46, ram=39, swap=0), minimum_disk_gib=45)
        self.assertEqual(result['extra_swap_gib'], 0)

    def test_separate_swap_and_docker_filesystems_checked_independently(self):
        result = PLAN(capacity(work=16), minimum_disk_gib=15,
                      swap_free_bytes=30 * GIB, docker_free_bytes=3 * GIB,
                      swap_shares_workspace=False, swap_shares_docker=False)
        self.assertEqual(result['workspace_free_after_swap_bytes'], 16 * GIB)
        for swap, docker in [(28, 3), (30, 1)]:
            with self.subTest(swap=swap, docker=docker), self.assertRaises(ValueError):
                PLAN(capacity(work=16), minimum_disk_gib=15,
                     swap_free_bytes=swap * GIB, docker_free_bytes=docker * GIB,
                     swap_shares_workspace=False, swap_shares_docker=False)

    def guard(self, space, command, directory):
        args = ['ci-guard-space.py', '--phase', 'test', '--minimum-free-gib', '2',
                '--poll-seconds', '0.05', '--log', str(directory / 'guard.jsonl'), '--', *command]
        with patch.object(sys, 'argv', args), patch('shutil.disk_usage', side_effect=space), patch('signal.signal'), redirect_stderr(io.StringIO()):
            return GUARD()

    def test_guard_propagates_success_and_failure(self):
        usage = shutil._ntuple_diskusage(100 * GIB, 0, 100 * GIB)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for exit_code in (0, 7):
                self.assertEqual(self.guard(lambda _: usage,
                    [sys.executable, '-c', f'raise SystemExit({exit_code})'], directory), exit_code)

    def test_guard_refuses_to_start_on_low_disk(self):
        usage = shutil._ntuple_diskusage(100 * GIB, 99 * GIB, GIB)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            marker = directory / 'started'
            status = self.guard(lambda _: usage,
                [sys.executable, '-c', f'from pathlib import Path; Path({str(marker)!r}).touch()'], directory)
            self.assertEqual(status, 125)
            self.assertFalse(marker.exists())

    def test_guard_stops_running_group_when_reserve_drops(self):
        calls = 0
        def space(_):
            nonlocal calls
            calls += 1
            return shutil._ntuple_diskusage(100 * GIB, 0, (100 if calls <= 2 else 1) * GIB)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            marker = directory / 'should-not-finish'
            status = self.guard(space, [sys.executable, '-c',
                f'import time; from pathlib import Path; time.sleep(10); Path({str(marker)!r}).touch()'], directory)
            self.assertEqual(status, 125)
            self.assertFalse(marker.exists())
            records = [json.loads(line) for line in (directory / 'guard.jsonl').read_text().splitlines()]
            self.assertEqual(records[-1]['event'], 'stopped-low-disk')


if __name__ == '__main__':
    unittest.main()
