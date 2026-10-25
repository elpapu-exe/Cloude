#!/usr/bin/env python3
"""Exercise the actual trial script against fake Android/sysfs and BusyBox.

No block devices are created. The copied script's block predicate, sysfs writer
and phone paths are substituted; allocation, sysfs effects and swap applets use fixtures. Reading
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
import json, os, shutil, subprocess, sys
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
        if ((mode == 'identity' and index == 0)
                or (mode == 'alias-identity' and Path(values[2]).parent == root / 'block')):
            index = 9
        print('fe:' + format(index, 'x'))
    elif values[:2] == ['-c', '%u']:
        print('0')  # Android fixture runs as root; the host test need not.
    elif values[:2] == ['-c', '%a']:
        print(format(Path(values[2]).stat().st_mode & 0o777, 'o'))
    else:
        sys.exit(subprocess.call(['/usr/bin/stat', *args]))
elif name == 'sysfs-write':
    path, value = Path(args[0]), args[1]
    event('sysfs-write', path=str(path), value=value)
    # Emulate an unbuffered sysfs store: a second bare newline is invalid.
    if '\n' in value or '\r' in value:
        sys.exit(22)
    if path.name == 'comp_algorithm' and mode == 'compressor':
        sys.exit(22)
    if path.name == 'disksize' and mode == 'disksize':
        sys.exit(22)
    if path.name == 'hot_remove':
        if mode == 'hot-remove':
            sys.exit(22)
        index = int(value)
        if index == 0:
            sys.exit(99)
        shutil.rmtree(root / f'sys/block/zram{index}')
        (root / f'dev/block/zram{index}').unlink(missing_ok=True)
    path.write_text(value)
    if path.name == 'hot_remove' and mode == 'hot-remove-partial':
        sys.exit(22)  # An error status alone must not hide successful removal.
elif name == 'cat':
    if len(args) == 1 and args[0] == str(root / 'sys/class/zram-control/hot_add'):
        index = int(os.environ.get('FIXTURE_NEW_ID', '1'))
        event('hot_add', index=index)
        if index != 0:
            base = f'sys/block/zram{index}'
            for field, value in {'dev': f'254:{index}\n', 'disksize': '0\n',
                                 'reset': '0\n', 'mm_stat': '0 0 0 0 0 0 0 0 0\n',
                                 'comp_algorithm': ('lzo [lzo-rle] lz4 lz4kd zstd\n'
                                     if mode == 'compressor' or os.environ.get('FIXTURE_DEFAULT_COMP') == 'lzo-rle'
                                     else 'lzo lzo-rle lz4 [lz4kd] zstd\n')}.items():
                put(f'{base}/{field}', value)
            put(f'dev/block/zram{index}', 'fake block device\n')
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
            print('awk\nmkswap\nswapon')
            sys.exit(0)
        applet, *args = args
    else:
        applet = name
    if applet == 'awk':
        sys.exit(subprocess.call(['/usr/bin/awk', *args]))
    event(applet, args=args)
    if applet == 'mkswap':
        if mode in ('mkswap', 'hot-remove', 'hot-remove-partial'):
            sys.exit(1)
    elif applet == 'swapon':
        if mode == 'swapon':
            sys.exit(1)
        if '-p' in args:
            priority = args[args.index('-p') + 1]
        else:
            entries = (root / 'proc/swaps').read_text().splitlines()[1:]
            priority = str(min([-1] + [int(line.split()[4]) for line in entries
                                     if int(line.split()[4]) < 0]) - 1)
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
        self.gate = self.lock.with_name(self.lock.name + '.apply')
        self.preexisting_gate = False
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
                     'mkswap', 'swapon', 'swapoff', 'sysfs-write']:
            command = self.put('bin/' + name, '#!' + sys.executable + '\n' + MOCK_COMMAND)
            command.chmod(0o755)
        busybox = self.put('data/adb/ksu/bin/busybox', '#!' + sys.executable + '\n' + MOCK_COMMAND)
        busybox.chmod(0o755)

        source = SCRIPT.read_text()
        writer = "write_sysfs() { printf '%s' \"$2\" > \"$1\"; }"
        self.assertEqual(source.count(writer), 1, 'Review the fixture if the sysfs writer changes')
        self.writer = writer
        source = source.replace(writer, 'write_sysfs() { sysfs-write "$1" "$2"; }')
        predicate = 'is_block_device() { [ -b "$1" ]; }'
        self.assertEqual(source.count(predicate), 1, 'Review the fixture if the block check changes')
        source = source.replace(predicate, 'is_block_device() { [ -f "$1" ]; }')
        source, count = re.subn(r'^PATH=[^\n]+$', f'PATH={bins}:/usr/bin:/bin',
                               source, count=1, flags=re.M)
        self.assertEqual(count, 1)
        # One pass prevents /proc/sys/... from being redirected a second time
        # when matching the /sys/ prefix inside that already rewritten path.
        prefixes = ['/data/adb/', '/data/local/tmp', '/sdcard/Download',
                    '/proc/', '/sys/', '/dev/block/', '/dev/zram', '/block/']
        # The /block alias must not match the tail of /sys/devices/virtual/block.
        source = re.sub(r'(?<![A-Za-z0-9_])(?:' + '|'.join(map(re.escape, prefixes)) + ')',
                        lambda match: str(self.root) + match[0], source)
        # Only the shell's own /proc liveness check uses the real host PID;
        # previous trial PIDs remain explicit fixture directories/dead PIDs.
        source = source.replace(f'[ -d "{self.root}/proc/$$" ]', '[ -d "/proc/$$" ]')
        self.script = self.put('trial.sh', source)
        self.original_zero = self.snapshot_zero()

    def put(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def snapshot_zero(self):
        paths = list((self.root / 'sys/block/zram0').iterdir()) + [self.base_device]
        alias = self.root / 'block/zram0'
        if alias.exists():
            paths.append(alias)
        return {str(path.relative_to(self.root)): path.read_bytes() for path in paths}

    def events(self):
        path = self.root / 'events.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_trial(self, mode='apply', *, fail='', **environment):
        env = dict(os.environ, FIXTURE_ROOT=str(self.root), FIXTURE_FAIL=fail, **environment)
        result = subprocess.run(['/bin/sh', str(self.script), mode], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(self.snapshot_zero(), self.original_zero, 'Existing zram0 was changed')
        self.assertEqual(self.gate.exists(), self.preexisting_gate, 'Apply gate ownership was violated')
        self.assertFalse(any(e['action'] == 'swapoff' for e in self.events()))
        for event in self.events():
            if event['action'] in ('mkswap', 'swapon'):
                self.assertNotEqual(event['args'][-1], str(self.base_device))
        return result

    def report(self):
        reports = list((self.root / 'sdcard/Download').glob('ChatGPTKernel-zRAM-*.txt'))
        return '\n'.join(path.read_text() for path in reports)

    def assert_inactive_new_removed(self):
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '1')
        self.assertFalse((self.root / 'sys/block/zram1').exists())
        self.assertFalse((self.root / 'dev/block/zram1').exists())
        self.assertEqual((self.root / 'proc/swaps').read_text(),
                         'Filename Type Size Used Priority\n' + self.base_row)
        self.assertFalse(self.lock.exists())

    def test_adds_one_gib_with_same_compressor_and_priority(self):
        result = self.run_trial()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + self.report())
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 1)
        self.assertEqual((self.root / 'sys/block/zram1/disksize').read_text(), str(GIB))
        self.assertEqual((self.root / 'sys/block/zram1/comp_algorithm').read_text(),
                         'lzo lzo-rle lz4 [lz4kd] zstd\n')
        self.assertFalse(any(e['action'] == 'sysfs-write' and Path(e['path']).name == 'comp_algorithm'
                             for e in self.events()))
        swaps = (self.root / 'proc/swaps').read_text()
        self.assertIn(self.base_row, swaps)
        self.assertIn(f'{self.root}/dev/block/zram1 partition 1048572 0 32758\n', swaps)
        sizes = [int(line.split()[2]) for line in swaps.splitlines()[1:]]
        self.assertEqual(sum(sizes) + 8, 3 * GIB // 1024)  # Two swap headers, 4 KiB each.
        self.assertEqual((self.root / 'sys/class/zram-control/hot_remove').read_text(), '')
        self.assertEqual((self.lock / 'state').read_text(), 'active\n')

    def configure_base(self, *, size=2642411520, alias='/block/zram0', priority=-2,
                       alias_exists=False):
        self.put('sys/block/zram0/disksize', str(size) + '\n')
        size_kib = size // 1024 - 4
        self.base_row = f'{self.root}{alias} partition {size_kib} 1000000 {priority}\n'
        self.put('proc/swaps', 'Filename Type Size Used Priority\n' + self.base_row)
        self.put('proc/meminfo', f'MemTotal: 3746720 kB\nMemAvailable: 800000 kB\n'
                 f'SwapTotal: {size_kib} kB\nSwapFree: {size_kib - 1000000} kB\n')
        if alias_exists:
            self.put(alias.removeprefix('/'), 'existing alias device: must not change\n')
        self.original_zero = self.snapshot_zero()

    def test_phone_alias_auto_priority_adds_only_missing_552_mib(self):
        self.configure_base()
        self.old_lock()
        result = self.run_trial()
        self.assertEqual(result.returncode, 0, self.report())
        self.assertEqual((self.root / 'sys/block/zram1/disksize').read_bytes(), b'578813952')
        self.assertIn(self.base_row, (self.root / 'proc/swaps').read_text())
        self.assertIn(f'{self.root}/dev/block/zram1 partition 565244 0 -3\n',
                      (self.root / 'proc/swaps').read_text())
        activation = [e for e in self.events() if e['action'] == 'swapon']
        self.assertEqual(len(activation), 1)
        self.assertEqual(activation[0]['args'], [str(self.root / 'dev/block/zram1')])
        sizes = [int(line.split()[2]) for line in (self.root / 'proc/swaps').read_text().splitlines()[1:]]
        self.assertEqual(sum(sizes) + 8, 3 * GIB // 1024)
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 1)

    def test_accessible_phone_alias_requires_matching_block_identity(self):
        self.configure_base(alias_exists=True)
        result = self.run_trial()
        self.assertEqual(result.returncode, 0, self.report())
        self.assertEqual((self.root / 'sys/block/zram1/disksize').read_bytes(), b'578813952')

    def test_wrong_accessible_alias_identity_is_not_silently_replaced(self):
        self.configure_base(alias_exists=True)
        result = self.run_trial(fail='alias-identity')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertFalse(self.lock.exists())

    def test_base_capacity_outside_supported_range_never_allocates(self):
        for size in [2 * GIB - 4096, 3 * GIB, 3 * GIB + 4096, 4 * GIB]:
            with self.subTest(size=size):
                self.configure_base(size=size)
                result = self.run_trial()
                self.assertNotEqual(result.returncode, 0, self.report())
                self.assertEqual(self.events(), [])
                self.assertFalse(self.lock.exists())

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

    def test_failed_removal_preserves_present_device_and_lock(self):
        result = self.run_trial(fail='hot-remove')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / 'sys/block/zram1').exists())
        self.assertTrue(self.lock.exists())
        self.assertIn('AFTER_FAILURE', self.report())
        before = self.events()
        retry = self.run_trial()
        self.assertNotEqual(retry.returncode, 0)
        self.assertEqual(self.events(), before)

    def test_error_status_after_successful_removal_can_be_recovered(self):
        result = self.run_trial(fail='hot-remove-partial')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'sys/block/zram1').exists())
        self.assertTrue(self.lock.exists())
        self.assertIn('AFTER_FAILURE', self.report())
        retry = self.run_trial()
        self.assertEqual(retry.returncode, 0, self.report())
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 2)
        self.assertEqual((self.lock / 'state').read_text(), 'active\n')

    def test_sysfs_writer_emits_only_the_value(self):
        target = self.root / 'writer-value'
        result = subprocess.run(['/bin/sh', '-c', self.writer + '\nwrite_sysfs "$1" "$2"',
                                 'fixture', str(target), 'lz4kd'], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b'lz4kd')

    def test_different_default_compressor_is_copied_without_newline(self):
        result = self.run_trial(FIXTURE_DEFAULT_COMP='lzo-rle')
        self.assertEqual(result.returncode, 0, self.report())
        writes = [e for e in self.events() if e['action'] == 'sysfs-write'
                  and Path(e['path']).name == 'comp_algorithm']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]['value'], 'lz4kd')
        self.assertEqual((self.root / 'sys/block/zram1/comp_algorithm').read_bytes(), b'lz4kd')

    def old_lock(self, *, pid='999999', state='allocating', index='1', boot='fixture-current-boot'):
        self.lock.mkdir(mode=0o700)
        for field, value in {'bootid': boot, 'pid': pid, 'state': state, 'created_id': index}.items():
            (self.lock / field).write_text(value + '\n')

    def test_recovers_only_absent_device_abandoned_lock(self):
        self.old_lock()
        result = self.run_trial()
        self.assertEqual(result.returncode, 0, result.stderr + self.report())
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 1)
        archives = list(self.lock.parent.glob(self.lock.name + '.previous-*'))
        self.assertEqual(len(archives), 1)
        self.assertEqual((archives[0] / 'metadata/state').read_text(), 'allocating\n')
        self.assertEqual((self.lock / 'state').read_text(), 'active\n')
        self.assertFalse(any(e['action'] == 'sysfs-write' and Path(e['path']).name == 'hot_remove'
                             for e in self.events()))

    def test_existing_apply_gate_is_preserved_without_allocation(self):
        self.gate.mkdir(mode=0o700)
        self.preexisting_gate = True
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue(self.gate.is_dir())
        self.assertFalse(self.lock.exists())

    def test_simultaneous_recovery_adds_only_one_device(self):
        self.old_lock()
        env = dict(os.environ, FIXTURE_ROOT=str(self.root), FIXTURE_FAIL='')
        children = [subprocess.Popen(['/bin/sh', str(self.script), 'apply'], env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for _ in range(2)]
        output = [child.communicate(timeout=15) for child in children]
        self.assertTrue(any(child.returncode == 0 for child in children), repr(output) + self.report())
        self.assertEqual(sum(e['action'] == 'hot_add' for e in self.events()), 1)
        self.assertEqual(self.snapshot_zero(), self.original_zero)
        self.assertFalse(any(e['action'] == 'swapoff' for e in self.events()))
        self.assertEqual((self.lock / 'state').read_text(), 'active\n')
        self.assertFalse(self.gate.exists())

    def test_present_inactive_device_prevents_lock_recovery(self):
        self.old_lock()
        self.put('sys/block/zram1/disksize', '0\n')
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue(self.lock.is_dir())
        self.assertEqual((self.lock / 'state').read_text(), 'allocating\n')

    def test_device_visible_only_in_virtual_sysfs_prevents_recovery(self):
        self.old_lock()
        self.put('sys/devices/virtual/block/zram1/disksize', '0\n')
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue(self.lock.is_dir())

    def test_other_extra_zram_prevents_lock_recovery(self):
        self.old_lock()
        self.put('sys/block/zram2/disksize', '0\n')
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue(self.lock.is_dir())

    def test_active_device_prevents_allocating_lock_recovery(self):
        self.old_lock()
        with (self.root / 'proc/swaps').open('a') as stream:
            stream.write(f'{self.root}/dev/block/zram1 partition 1048572 0 32758\n')
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue(self.lock.is_dir())

    def test_live_pid_prevents_lock_recovery(self):
        self.old_lock(pid=str(os.getpid()))
        (self.root / f'proc/{os.getpid()}').mkdir()
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue(self.lock.is_dir())

    def test_invalid_metadata_prevents_lock_recovery(self):
        for changes in [{'pid': '0'}, {'pid': '-1'}, {'pid': '01'}, {'index': '0'},
                        {'index': '01'}, {'state': 'activating'}, {'boot': 'other-boot'}]:
            with self.subTest(changes=changes):
                if self.lock.exists():
                    for entry in self.lock.iterdir():
                        entry.unlink()
                    self.lock.rmdir()
                self.old_lock(**changes)
                result = self.run_trial()
                self.assertNotEqual(result.returncode, 0, self.report())
                self.assertEqual(self.events(), [])
                self.assertTrue(self.lock.is_dir())

    def test_symlink_metadata_prevents_lock_recovery(self):
        self.old_lock()
        (self.lock / 'created_id').unlink()
        target = self.put('external-created-id', '1\n')
        (self.lock / 'created_id').symlink_to(target)
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])
        self.assertTrue((self.lock / 'created_id').is_symlink())
        self.assertEqual(target.read_bytes(), b'1\n')

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
