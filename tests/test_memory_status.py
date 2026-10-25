#!/usr/bin/env python3
"""Exercise the read-only memory snapshot with kernel logs and Android fixtures."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/chatgpt-memory-status.sh'


class MemoryStatusTests(unittest.TestCase):
    def run_snapshot(self, *, kernel='', fallback='', denied=False, missing_awk=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def put(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
                return path

            fixtures = {
                'proc/uptime': '600.00 2000.00\n',
                'proc/sys/kernel/random/boot_id': 'fixture-current-boot\n',
                'proc/meminfo': 'MemTotal: 3746720 kB\nMemAvailable: 800000 kB\nSwapTotal: 3145720 kB\nSwapFree: 9000 kB\n',
                'proc/swaps': 'Filename Type Size Used Priority\n/block/zram0 partition 2580476 2235920 -2\n/dev/block/zram1 partition 565244 400000 -3\n',
                'proc/pressure/memory': 'some avg10=10.00 total=1000\nfull avg10=8.00 total=500\n',
                'proc/sys/vm/min_free_kbytes': '8192\n',
                'proc/sys/vm/watermark_scale_factor': '1\n',
                'proc/sys/vm/swappiness': '100\n',
                'proc/sys/vm/page-cluster': '0\n',
                'proc/sys/vm/oom_dump_tasks': '1\n',
                'proc/sys/vm/oom_kill_allocating_task': '0\n',
                'proc/sys/vm/overcommit_memory': '1\n',
                'proc/buddyinfo': 'Node 0, zone Normal 10 2 1 0 0 0 0 0 0 0 0\n',
                'proc/zoneinfo': 'Node 0, zone Normal\n  pages free 8100\n  min 2048\n',
                'proc/vmstat': 'oom_kill 5\nallocstall_normal 20\npswpin 10\npswpout 30\n',
                'sys/block/zram0/disksize': '2642411520\n',
                'sys/block/zram1/disksize': '578813952\n',
            }
            for name, value in fixtures.items():
                put(name, value)
            (root / 'Download').mkdir()
            (root / 'tmp').mkdir()
            (root / 'bin').mkdir()
            kernel_path = put('kernel-fixture', kernel)
            fallback_path = put('fallback-fixture', fallback)
            calls = put('calls', '')
            commands = {
                'id': 'printf "0\\n"',
                'uname': 'printf "fixture-kernel\\n"',
                'dmesg': '''printf 'dmesg %s\\n' "$*" >> "$FIXTURE_CALLS"
[ "$#" -eq 0 ] || exit 99
if [ "$FIXTURE_DENIED" = 1 ]; then
  printf 'dmesg: read kernel buffer failed: Operation not permitted\\n' >&2
  exit 1
fi
cat "$FIXTURE_KERNEL"''',
                'logcat': '''printf 'logcat %s\\n' "$*" >> "$FIXTURE_CALLS"
[ "$*" = '-d -b kernel -v monotonic' ] || exit 99
if [ "$FIXTURE_DENIED" = 1 ] && [ -z "$FIXTURE_HAS_FALLBACK" ]; then
  printf 'kernel logcat: Permission denied\\n' >&2
  exit 1
fi
cat "$FIXTURE_FALLBACK"''',
            }
            for name, body in commands.items():
                path = put('bin/' + name, '#!/bin/sh\n' + body + '\n')
                path.chmod(0o755)
            busybox = put('busybox', '''#!/bin/sh
if [ "$1" = --list ]; then
  [ "$FIXTURE_MISSING_AWK" = 1 ] || printf 'awk\\n'
  exit 0
fi
[ "$1" = awk ] || exit 99
shift
exec /usr/bin/awk "$@"
''')
            busybox.chmod(0o755)
            source = SCRIPT.read_text()
            source, count = re.subn(r'^PATH=[^\n]+$', f'PATH={root / "bin"}:/usr/bin:/bin',
                                    source, count=1, flags=re.M)
            self.assertEqual(count, 1)
            source = source.replace('/data/adb/ksu/bin/busybox', str(busybox))
            replacements = {'/sdcard/Download': str(root / 'Download'),
                            '/data/local/tmp': str(root / 'tmp'),
                            '/proc/': str(root / 'proc') + '/',
                            '/sys/': str(root / 'sys') + '/'}
            # One pass keeps /proc/sys/ from acquiring two fixture prefixes.
            source = re.sub('|'.join(map(re.escape, replacements)),
                            lambda match: replacements[match[0]], source)
            script = put('snapshot.sh', source)
            before = {str(path.relative_to(root)): path.read_bytes()
                      for group in ['proc', 'sys'] for path in (root / group).rglob('*')
                      if path.is_file()}
            environment = dict(os.environ, FIXTURE_KERNEL=str(kernel_path),
                               FIXTURE_FALLBACK=str(fallback_path), FIXTURE_CALLS=str(calls),
                               FIXTURE_DENIED='1' if denied else '0',
                               FIXTURE_HAS_FALLBACK='1' if fallback else '',
                               FIXTURE_MISSING_AWK='1' if missing_awk else '0')
            result = subprocess.run(['/bin/sh', str(script)], env=environment,
                                    capture_output=True, text=True, timeout=8)
            reports = list((root / 'Download').glob('ChatGPTKernel-memoria-*.txt'))
            self.assertEqual(len(reports), 1, result.stdout + result.stderr)
            report = reports[0].read_text()
            self.assertGreater(len(report), 300)
            self.assertIn('Read-only memory and kernel-log snapshot', report)
            self.assertIn('MemAvailable: 800000 kB', report)
            self.assertIn('/block/zram0 partition 2580476', report)
            self.assertIn('min_free_kbytes: 8192', report)
            self.assertIn('Report: ' + str(reports[0]), result.stdout)
            after = {str(path.relative_to(root)): path.read_bytes()
                     for group in ['proc', 'sys'] for path in (root / group).rglob('*')
                     if path.is_file()}
            self.assertEqual(after, before, 'A system fixture was modified')
            self.assertEqual(list((root / 'tmp').iterdir()), [], 'Private raw logs were not cleaned')
            called = calls.read_text().splitlines()
            for call in called:
                self.assertIn(call.strip(), ['dmesg', 'logcat -d -b kernel -v monotonic'])
            return result, report

    def test_no_oom_produces_nonempty_report_with_explicit_coverage(self):
        result, report = self.run_snapshot(kernel='[    1.000] UNRELATED_PRIVATE_LINE\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn('dmesg exit status: 0', report)
        self.assertIn('Lines read: 1', report)
        self.assertIn('First kernel timestamp: 1.000', report)
        self.assertEqual(report.count('No matching OOM context remains in this source.'), 2)
        self.assertNotIn('UNRELATED_PRIVATE_LINE', report)
        self.assertIn('SNAPSHOT FINISHED', report)

    def test_denied_log_sources_still_leave_complete_nonempty_diagnostic(self):
        result, report = self.run_snapshot(denied=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('dmesg exit status: 1', report)
        self.assertIn('Kernel buffer could not be read.', report)
        self.assertIn('kernel logcat exit status: 1', report)
        self.assertIn('Kernel logcat source unavailable.', report)
        self.assertNotIn('No matching OOM context remains', report)
        self.assertIn('SNAPSHOT FINISHED', report)

    def test_last_two_oom_blocks_keep_bounded_context_and_omit_task_tables(self):
        kernel = '[1.000] OLDEST invoked oom-killer: gfp_mask=0\n'
        kernel += '[1.100] Tasks state (memory values in pages):\n'
        kernel += '[1.200] SECRET_OLDEST_TASK_TABLE\n'
        kernel += '[1.300] Out of memory: Killed process 1 (OLDEST_KILL)\n'
        kernel += '[2.000] MIDDLE invoked oom-killer: gfp_mask=0\n'
        kernel += ''.join(f'[2.{index + 1:03d}] MIDDLE_CONTEXT_{index:03d}\n'
                          for index in range(120))
        kernel += '[2.500] Tasks state (memory values in pages):\n'
        kernel += '[2.600] SECRET_MIDDLE_TASK_TABLE\n'
        kernel += '[2.700] oom-kill:constraint=CONSTRAINT_NONE,task=MIDDLE\n'
        kernel += '[2.800] Out of memory: Killed process 2 (MIDDLE_KILL)\n'
        kernel += '[3.000] NEWEST invoked oom-killer: gfp_mask=0\n'
        kernel += '[3.100] Mem-Info: free:1000\n'
        kernel += '[3.200] Tasks state (memory values in pages):\n'
        kernel += '[3.300] SECRET_NEWEST_TASK_TABLE\n'
        kernel += '[3.400] Out of memory: Killed process 3 (NEWEST_KILL)\n'
        kernel += '[4.000] SECRET_UNRELATED_AFTER_OOM\n'
        result, report = self.run_snapshot(kernel=kernel)
        self.assertEqual(result.returncode, 0)
        self.assertIn('OOM headers: 3 kill summaries: 3 captured blocks: 3', report)
        self.assertIn('MIDDLE invoked oom-killer', report)
        self.assertIn('NEWEST invoked oom-killer', report)
        self.assertIn('MIDDLE_CONTEXT_098', report)
        self.assertNotIn('MIDDLE_CONTEXT_099', report)
        self.assertIn('oom-kill:constraint=CONSTRAINT_NONE,task=MIDDLE', report)
        self.assertIn('MIDDLE_KILL', report)
        self.assertIn('NEWEST_KILL', report)
        self.assertNotIn('OLDEST invoked', report)
        self.assertNotIn('OLDEST_KILL', report)
        self.assertNotIn('Tasks state', report)
        self.assertNotIn('SECRET_', report)

    def test_kernel_logcat_fallback_can_recover_standalone_kill_summary(self):
        fallback = '[9.000] oom-kill:constraint=CONSTRAINT_NONE,task=FALLBACK\n'
        fallback += '[9.100] Out of memory: Killed process 4 (FALLBACK_KILL)\n'
        result, report = self.run_snapshot(denied=True, fallback=fallback)
        self.assertEqual(result.returncode, 0)
        self.assertIn('dmesg exit status: 1', report)
        self.assertIn('kernel logcat exit status: 0', report)
        self.assertIn('OOM headers: 0 kill summaries: 1 captured blocks: 1', report)
        self.assertIn('FALLBACK_KILL', report)
        self.assertIn('SNAPSHOT FINISHED', report)

    def test_missing_awk_still_reports_memory_and_explicit_failure(self):
        result, report = self.run_snapshot(missing_awk=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('KernelSU BusyBox awk unavailable; kernel log not read.', report)
        self.assertNotIn('dmesg exit status:', report)


if __name__ == '__main__':
    unittest.main()
