#!/usr/bin/env python3
"""Exercise the actual trial script against fake Android/sysfs and BusyBox.

No block devices are created. Only the copied script's S_IFBLK predicate and
phone paths are substituted; allocation and swap applets use fixtures. Reading
hot_add is instrumented because that read itself allocates a kernel device.
"""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/chatgpt-zram-try.sh'
GIB = 1024 ** 3

MOCK_COMMAND = r'''
import json, os, subprocess, sys
from pathlib import Path

root = Path(os.environ['FIXTURE_ROOT'])
name = Path(sys.argv[0]).name
args = sys.argv[1:]
mode = os.environ.get('FIXTURE_FAIL', '')

def event(action, **details):
    with (root / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action=action, **details)) + '\n')

def put(path, value):
    path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)

if name == 'id':
    print(os.environ.get('FIXTURE_UID', '0'))
elif name == 'getprop':
    print({'ro.product.device': os.environ.get('FIXTURE_DEVICE', 'tapas'),
           'ro.build.version.sdk': os.environ.get('FIXTURE_SDK', '33')}.get(args[0], ''))
elif name == 'dumpsys':
    print('    versionCode=10 minSdk=28 targetSdk=34\n    versionName=fixture')
elif name == 'sleep':
    pass
elif name == 'stat':
    values = [value for value in args if value != '-L']
    if values[:2] == ['-c', '%t:%T']:
        index = int(Path(values[2]).name.removeprefix('zram'))
        if mode == 'identity' and index == 0:
            index = 9
        print('fe:' + format(index, 'x'))
    elif values[:2] == ['-c', '%u']:
        print('0')  # Android fixture runs as root; the host test need not.
    elif values[:2] == ['-c', '%a']:
        print(format(Path(values[2]).stat().st_mode & 0o777, 'o'))
    else:
        sys.exit(subprocess.call(['/usr/bin/stat', *args]))
elif name == 'cat':
    if len(args) == 1 and args[0] == str(root / 'sys/class/zram-control/hot_add'):
        index = int(os.environ.get('FIXTURE_NEW_ID', '1'))
        event('hot_add', index=index)
        if index != 0:
            base = f'sys/block/zram{index}'
            for field, value in {'dev': f'254:{index}\n', 'disksize': '0\n',
                                 'reset': '0\n', 'mm_stat': '0 0 0 0 0 0 0 0 0\n',
                                 'comp_algorithm': 'lzo [lzo-rle] lz4 lz4kd zstd\n'}.items():
                put(f'{base}/{field}', value)
            put(f'dev/block/zram{index}', 'fake block device\n')
            if mode == 'compressor':
                path = root / base / 'comp_algorithm'
                path.unlink()
                path.mkdir()  # A redirect here must fail, as a sysfs write may.
        print(index)
    elif len(args) == 1 and Path(args[0]).name == 'comp_algorithm':
        path = Path(args[0])
        try:
            value = path.read_text().strip()
        except OSError:
            sys.exit(1)
        if '[' not in value:
            # A real sysfs read returns its algorithm list after selecting one.
            value = ' '.join(f'[{x}]' if x == value else x
                             for x in ['lzo', 'lzo-rle', 'lz4', 'lz4kd', 'zstd'])
        print(value)
    else:
        sys.exit(subprocess.call(['/bin/cat', *args]))
elif name in ('busybox', 'mkswap', 'swapon', 'swapoff'):
    if name == 'busybox':
        if args == ['--list']:
            print('mkswap\nswapon')
            sys.exit(0)
        applet, *args = args
    else:
        applet = name
    event(applet, args=args)
    if applet == 'mkswap':
        if mode == 'mkswap':
            sys.exit(1)
    elif applet == 'swapon':
        if mode == 'swapon':
            sys.exit(1)
        priority = args[args.index('-p') + 1]
        device = args[-1]
        index = int(Path(device).name.removeprefix('zram'))
        size = int((root / f'sys/block/zram{index}/disksize').read_text()) // 1024 - 4
        with (root / 'proc/swaps').open('a') as stream:
            stream.write(f'{device} partition {size} 0 {priority}\n')
        if mode == 'swapon-active-error':
            sys.exit(1)  # A failed command is not proof that swap is inactive.
        if mode == 'swapon-ambiguous':
            (root / 'proc/swaps').write_text('unreadable-or-malformed-swap-state\n')
            sys.exit(1)
    else:
        # Never allow a real or simulated swapoff, including an unexpected call.
        sys.exit(99)
else:
    sys.exit(127)
'''


class ZramTrialTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.lock = self.root / 'data/local/tmp/chatgpt-zram-try-fixture-current-boot.lock'
        self.put('proc/uptime', '600.00 2000.00\n')
        self.put('proc/sys/kernel/random/boot_id', 'fixture-current-boot\n')
        self.put('proc/meminfo', 'MemTotal: 3746720 kB\nMemAvailable: 800000 kB\n'
                 'SwapTotal: 2097148 kB\nSwapFree: 100000 kB\n')
        self.put('proc/pressure/memory', 'some avg10=20.00 total=1000\nfull avg10=10.00 total=500\n')
        self.base_device = self.root / 'dev/block/zram0'
        self.base_row = f'{self.base_device} partition 2097148 1997148 32758\n'
        self.put('proc/swaps', 'Filename Type Size Used Priority\n' + self.base_row)
        for field, value in {'dev': '254:0\n', 'disksize': f'{2 * GIB}\n',
                             'reset': '0\n', 'mm_stat': '100 50 60 0 70 0 0 0 0\n',
                             'comp_algorithm': 'lzo lzo-rle lz4 [lz4kd] zstd\n'}.items():
            self.put('sys/block/zram0/' + field, value)
        self.put('dev/block/zram0', 'original fake block device: must not change\n')
        self.put('sys/class/zram-control/hot_add', '1\n')
        self.put('sys/class/zram-control/hot_remove', '')
        (self.root / 'sdcard/Download').mkdir(parents=True)
        (self.root / 'data/local/tmp').mkdir(parents=True)
        bins = self.root / 'bin'
        bins.mkdir()
        for name in ['id', 'getprop', 'dumpsys', 'sleep', 'stat', 'cat',
                     'mkswap', 'swapon', 'swapoff']:
            command = self.put('bin/' + name, '#!' + sys.executable + '\n' + MOCK_COMMAND)
            command.chmod(0o755)
        busybox = self.put('data/adb/ksu/bin/busybox', '#!' + sys.executable + '\n' + MOCK_COMMAND)
        busybox.chmod(0o755)

        source = SCRIPT.read_text()
        predicate = 'is_block_device() { [ -b "$1" ]; }'
        self.assertEqual(source.count(predicate), 1, 'Review the fixture if the block check changes')
        source = source.replace(predicate, 'is_block_device() { [ -f "$1" ]; }')
        source, count = re.subn(r'^PATH=[^\n]+$', f'PATH={bins}:/usr/bin:/bin',
                               source, count=1, flags=re.M)
        self.assertEqual(count, 1)
        # One pass prevents /proc/sys/... from being redirected a second time
        # when matching the /sys/ prefix inside that already rewritten path.
        prefixes = ['/data/adb/', '/data/local/tmp', '/sdcard/Download',
                    '/proc/', '/sys/', '/dev/block/', '/dev/zram']
        source = re.sub('|'.join(map(re.escape, prefixes)),
                        lambda match: str(self.root) + match[0], source)
        self.script = self.put('trial.sh', source)
        self.original_zero = self.snapshot_zero()

    def put(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def snapshot_zero(self):
        paths = list((self.root / 'sys/block/zram0').iterdir()) + [self.base_device]
        return {str(path.relative_to(self.root)): path.read_bytes() for path in paths}

    def events(self):
        path = self.root / 'events.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_trial(self, mode='apply', *, fail='', **environment):
        env = dict(os.environ, FIXTURE_ROOT=str(self.root), FIXTURE_FAIL=fail, **environment)
        result = subprocess.run(['/bin/sh', str(self.script), mode], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(self.snapshot_zero(), self.original_zero, 'Existing zram0 was changed')
        self.assertFalse(any(e['action'] == 'swapoff' for e in self.events()))
        for event in self.events():
            if event['action'] in ('mkswap', 'swapon'):
                self.assertNotEqual(event['args'][-1], str(self.base_device))
        return result

    def report(self):
        reports = list((self.root / 'sdcard/Download').glob('ChatGPTKernel-zRAM-*.txt'))
        return '\n'.join(path.read_text() for path in reports)

    def assert_inactive_new_removed(self):
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '1\n')
        self.assertEqual((self.root / 'sys/block/zram1/reset').read_text(), '0\n')
        self.assertEqual((self.root / 'proc/swaps').read_text(),
                         'Filename Type Size Used Priority\n' + self.base_row)
        self.assertFalse(self.lock.exists())

    def test_adds_one_gib_with_same_compressor_and_priority(self):
        result = self.run_trial()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + self.report())
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 1)
        self.assertEqual((self.root / 'sys/block/zram1/disksize').read_text(), f'{GIB}\n')
        self.assertEqual((self.root / 'sys/block/zram1/comp_algorithm').read_text(), 'lz4kd\n')
        swaps = (self.root / 'proc/swaps').read_text()
        self.assertIn(self.base_row, swaps)
        self.assertIn(f'{self.root}/dev/block/zram1 partition 1048572 0 32758\n', swaps)
        sizes = [int(line.split()[2]) for line in swaps.splitlines()[1:]]
        self.assertEqual(sum(sizes) + 8, 3 * GIB // 1024)  # Two swap headers, 4 KiB each.
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')
        self.assertEqual((self.lock / 'state').read_text(), 'active\n')

    def test_duplicate_does_not_allocate_another_device(self):
        first = self.run_trial()
        self.assertEqual(first.returncode, 0, self.report())
        before = (self.root / 'proc/swaps').read_bytes()
        second = self.run_trial()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr + self.report())
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 1)
        self.assertEqual((self.root / 'proc/swaps').read_bytes(), before)
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')

    def test_preflight_failures_never_read_hot_add(self):
        cases = [('low-memory', {}, 'MemAvailable: 524287 kB\n'),
                 ('identity', {}, None), ('wrong-device', {'FIXTURE_DEVICE': 'other'}, None),
                 ('wrong-sdk', {'FIXTURE_SDK': '34'}, None),
                 ('nonroot', {'FIXTURE_UID': '2000'}, None)]
        for failure, env, meminfo in cases:
            with self.subTest(failure=failure):
                original = (self.root / 'proc/meminfo').read_text()
                if meminfo is not None:
                    self.put('proc/meminfo', meminfo)
                result = self.run_trial(fail=failure, **env)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.events(), [])
                self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')
                self.put('proc/meminfo', original)

    def test_mkswap_failure_removes_only_owned_inactive_device(self):
        result = self.run_trial(fail='mkswap')
        self.assertNotEqual(result.returncode, 0)
        self.assert_inactive_new_removed()
        self.assertFalse(any(e['action'] == 'swapon' for e in self.events()))

    def test_swapon_failure_removes_only_owned_inactive_device(self):
        result = self.run_trial(fail='swapon')
        self.assertNotEqual(result.returncode, 0)
        self.assert_inactive_new_removed()

    def test_compressor_failure_removes_only_owned_inactive_device(self):
        result = self.run_trial(fail='compressor')
        self.assertNotEqual(result.returncode, 0)
        self.assert_inactive_new_removed()
        self.assertFalse(any(e['action'] in ('mkswap', 'swapon') for e in self.events()))

    def test_swapon_error_does_not_remove_device_that_became_active(self):
        result = self.run_trial(fail='swapon-active-error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(self.root / 'dev/block/zram1'), (self.root / 'proc/swaps').read_text())
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')
        self.assertTrue(self.lock.exists())

    def test_ambiguous_swap_state_does_not_remove_new_device(self):
        result = self.run_trial(fail='swapon-ambiguous')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')
        self.assertTrue(self.lock.exists())

    def test_hot_add_returning_zero_never_removes_original_device(self):
        result = self.run_trial(FIXTURE_NEW_ID='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')
        self.assertFalse(any(e['action'] in ('mkswap', 'swapon') for e in self.events()))

    def test_status_is_read_only_even_when_trial_is_active(self):
        first = self.run_trial()
        self.assertEqual(first.returncode, 0, self.report())
        events_before = self.events()
        before = {str(p.relative_to(self.root)): p.read_bytes()
                  for group in ['sys', 'proc', 'dev', 'data/local/tmp']
                  for p in (self.root / group).rglob('*')
                  if p.is_file()}
        result = self.run_trial('status')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + self.report())
        after = {str(p.relative_to(self.root)): p.read_bytes()
                 for group in ['sys', 'proc', 'dev', 'data/local/tmp']
                 for p in (self.root / group).rglob('*')
                 if p.is_file()}
        self.assertEqual(after, before)
        self.assertEqual(self.events(), events_before)
        self.assertIn('Read-only zRAM status captured', result.stdout)


if __name__ == '__main__':
    unittest.main()
