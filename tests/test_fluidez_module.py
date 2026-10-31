#!/usr/bin/env python3
"""Exercise the real memory module using isolated Android files and command stubs.

Only paths and PATH are changed in the copied script. No phone, root privilege,
production test hooks, kernel build, or GitHub workflow is used.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / 'modules/chatgpt-fluidez-memoria/bin/control.sh'


class PhoneFixture:
    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='fluidez-module-test-')
        self.root = Path(self.temporary.name)
        self.bins = self.root / 'bin'
        self.bins.mkdir()
        self.state = self.root / 'data/adb/chatgpt-fluidez-memoria'
        self.module = self.root / 'data/adb/modules/chatgpt-fluidez-memoria'
        self.mglru = self.put('sys/kernel/mm/lru_gen/enabled', '0x0002\n')
        self.watermark = self.put('proc/sys/vm/watermark_scale_factor', '10\n')
        self.boot_id = self.put('proc/sys/kernel/random/boot_id', '00000000-0000-4000-8000-000000000001\n')
        self.put('proc/meminfo', 'MemTotal: 3744164 kB\nMemAvailable: 620612 kB\nSwapTotal: 3145724 kB\nSwapFree: 8996 kB\n')
        self.put('proc/pressure/memory', 'some avg10=1.0 total=100\nfull avg10=0.1 total=10\n')
        self.put('proc/uptime', '100.0 200.0\n')
        self.put('proc/mounts', '/dev/block/dm-3 /data f2fs rw 0 0\n')
        self.put('Download/.keep', '')
        self.sentinels = {
            'proc/sys/vm/swappiness': '100\n',
            'sys/block/zram0/disksize': '3221225472\n',
            'sys/block/zram0/comp_algorithm': 'lzo lz4 [lz4kd]\n',
            'sys/devices/system/cpu/cpufreq/policy0/scaling_governor': 'schedutil\n',
            'sys/class/thermal/thermal_zone0/temp': '42000\n',
            'data/adb/modules/LSPosed/module.prop': 'id=LSPosed\n',
            'data/adb/modules/NeoZygisk/module.prop': 'id=NeoZygisk\n',
        }
        for name, value in self.sentinels.items():
            self.put(name, value)
        self.environment = dict(os.environ,
            FIXTURE_UID='0', FIXTURE_DEVICE='tapas', FIXTURE_SDK='33',
            FIXTURE_MACHINE='aarch64', FIXTURE_RELEASE='5.15.216-ChatGPTKernel-0.1.0-rc4',
            FIXTURE_BOOT_COMPLETE='1', FIXTURE_ROOT=str(self.root),
            FIXTURE_BLOCK_CAT='', FIXTURE_DENY_WRITE='', FIXTURE_FAIL_AFTER_WRITE='',
            FIXTURE_CAT_REACHED=str(self.root / 'cat-reached'),
            FIXTURE_CAT_RELEASE=str(self.root / 'cat-release'),
            FIXTURE_SLEEP_LOG=str(self.root / 'sleep-calls'),
            PATH=str(self.bins) + ':/usr/bin:/bin')
        self.stub('id', 'if [ "$1" = -u ]; then printf "%s\\n" "$FIXTURE_UID"; else /usr/bin/id "$@"; fi')
        self.stub('uname', '''case "$1" in
-m) printf '%s\\n' "$FIXTURE_MACHINE";;
-r) printf '%s\\n' "$FIXTURE_RELEASE";;
*) printf 'Linux fixture %s %s\\n' "$FIXTURE_RELEASE" "$FIXTURE_MACHINE";;
esac''')
        self.stub('getprop', '''case "$1" in
ro.product.device|ro.product.vendor.device|ro.product.system.device|ro.product.product.device) printf '%s\\n' "$FIXTURE_DEVICE";;
ro.build.version.sdk) printf '%s\\n' "$FIXTURE_SDK";;
ro.product.cpu.abi) printf 'arm64-v8a\\n';;
sys.boot_completed) printf '%s\\n' "$FIXTURE_BOOT_COMPLETE";;
ro.build.display.id) printf 'lineage_topaz fixture\\n';;
esac''')
        self.stub('sleep', 'printf "%s\\n" "$*" >> "$FIXTURE_SLEEP_LOG"')
        self.stub('sh', r'''last=
for arg in "$@"; do last=$arg; done
if [ -n "$FIXTURE_DENY_WRITE" ] && [ "$last" = "$FIXTURE_DENY_WRITE" ]; then exit 1; fi
/bin/sh "$@"
result=$?
if [ "$result" -eq 0 ] && [ -n "$FIXTURE_FAIL_AFTER_WRITE" ] && [ "$last" = "$FIXTURE_FAIL_AFTER_WRITE" ]; then exit 1; fi
exit "$result"''')
        self.stub('cat', r'''for arg in "$@"; do
  if [ -n "$FIXTURE_BLOCK_CAT" ] && [ "$arg" = "$FIXTURE_BLOCK_CAT" ]; then
    : > "$FIXTURE_CAT_REACHED"
    count=0
    while [ ! -e "$FIXTURE_CAT_RELEASE" ]; do
      /usr/bin/sleep 0.01
      count=$((count + 1))
      [ "$count" -lt 500 ] || exit 124
    done
  fi
done
exec /usr/bin/cat "$@"''')
        self.install_control()

    def put(self, relative, value):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
        return target

    def stub(self, name, body):
        path = self.bins / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def install_control(self, upgrade=False):
        if upgrade:
            self.module = self.root / 'data/adb/modules/chatgpt-fluidez-memoria-upgraded'
        script = self.module / 'bin/control.sh'
        script.parent.mkdir(parents=True, exist_ok=True)
        source = CONTROL.read_text()
        # Rewrite filesystem selectors only; keep the production decision logic.
        replacements = {
            '/data/adb': str(self.root / 'data/adb'),
            '/proc/': str(self.root / 'proc') + '/',
            '/sys/': str(self.root / 'sys') + '/',
            '/sdcard/Download': str(self.root / 'Download'),
            '/data/local/tmp': str(self.root / 'data/local/tmp'),
            '/system/bin/sh': '/bin/sh',
        }
        # One pass prevents rewriting the /sys/ suffix inside a remapped /proc/sys/.
        source = re.sub('|'.join(re.escape(key) for key in replacements),
                        lambda match: replacements[match.group()], source)
        fixture_path = str(self.bins) + ':/usr/bin:/bin'
        source = re.sub(r'(?m)^(export )?PATH=.*$', 'PATH=' + fixture_path + '\nexport PATH', source)
        script.write_text(source)
        script.chmod(0o755)
        (self.module / 'module.prop').write_text('id=chatgpt-fluidez-memoria\nname=Fixture\nversion=fixture\n')
        self.script = script

    def run(self, action, **changes):
        env = dict(self.environment, **changes)
        return subprocess.run(['/bin/sh', str(self.script), action], env=env,
                              capture_output=True, text=True, timeout=8)

    def start(self, action, **changes):
        return subprocess.Popen(['/bin/sh', str(self.script), action],
                                env=dict(self.environment, **changes),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def values(self):
        def number(path):
            value = path.read_text().strip()
            return int(value, 16 if value.lower().startswith('0x') else 10)
        return number(self.mglru), number(self.watermark)

    def assert_sentinels(self, testcase):
        for name, value in self.sentinels.items():
            testcase.assertEqual((self.root / name).read_text(), value, name)

    def close(self):
        self.temporary.cleanup()


class FluidezModuleTests(unittest.TestCase):
    def setUp(self):
        self.phone = PhoneFixture()
        self.addCleanup(self.phone.close)

    def ok(self, action, **changes):
        result = self.phone.run(action, **changes)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.phone.assert_sentinels(self)
        return result

    def test_apply_is_idempotent_and_preserves_baseline_across_upgrade(self):
        self.ok('apply')
        self.assertEqual(self.phone.values(), (3, 64))
        self.assertTrue(self.phone.state.is_dir())
        self.assertFalse(self.phone.state.is_relative_to(self.phone.module))
        self.assertEqual(self.phone.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.phone.state / 'session').stat().st_mode & 0o777, 0o700)
        self.ok('apply')
        self.phone.install_control(upgrade=True)
        self.ok('apply')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_topaz_is_supported(self):
        self.ok('apply', FIXTURE_DEVICE='topaz')
        self.assertEqual(self.phone.values(), (3, 64))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_restore_preserves_third_party_changes(self):
        self.ok('apply')
        self.phone.mglru.write_text('7\n')
        self.phone.watermark.write_text('128\n')
        self.ok('apply')
        self.assertEqual(self.phone.values(), (7, 128))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (7, 128))

    def test_restore_changes_only_knob_still_at_our_target(self):
        self.ok('apply')
        self.phone.watermark.write_text('90\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 90))

    def test_reboot_does_not_restore_stale_values_and_takes_fresh_baseline(self):
        self.ok('apply')
        self.phone.boot_id.write_text('00000000-0000-4000-8000-000000000002\n')
        self.phone.mglru.write_text('0x0004\n')
        self.phone.watermark.write_text('1\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (4, 1))
        self.ok('apply')
        self.assertEqual(self.phone.values(), (5, 64))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (4, 1))

    def test_mglru_mask_preserves_other_bits(self):
        for old, applied in ((0, 1), (2, 3), (4, 5), (7, 7)):
            with self.subTest(mask=old):
                self.phone.mglru.write_text(f'0x{old:04x}\n')
                self.ok('apply')
                self.assertEqual(self.phone.values()[0], applied)
                self.ok('restore')
                self.assertEqual(self.phone.values()[0], old)

    def test_mglru_rejects_large_invalid_masks_and_accepts_padded_forms(self):
        for raw in ('4294967296', '0x100000000', '8', '0x0008', '-1', '0xg', 'invalid'):
            with self.subTest(invalid_mask=raw):
                self.phone.mglru.write_text(raw + '\n')
                self.ok('apply')
                self.assertEqual(self.phone.mglru.read_text(), raw + '\n')
                self.assertFalse((self.phone.state / 'session/mglru').exists())
                self.ok('restore')
                self.assertEqual(self.phone.mglru.read_text(), raw + '\n')
        for raw, applied, original in (('0002', 3, 2), ('0X0004', 5, 4)):
            with self.subTest(valid_mask=raw):
                self.phone.mglru.write_text(raw + '\n')
                self.ok('apply')
                self.assertEqual(self.phone.values()[0], applied)
                self.ok('restore')
                self.assertEqual(self.phone.values()[0], original)
        sleep_log = Path(self.phone.environment['FIXTURE_SLEEP_LOG'])
        self.assertFalse(sleep_log.exists(), 'Apply/restore must not start an enforcement loop')

    def test_watermark_floor_and_existing_headroom(self):
        for old, applied in ((1, 64), (10, 64), (64, 64), (128, 128)):
            with self.subTest(watermark=old):
                self.phone.watermark.write_text(str(old) + '\n')
                self.ok('apply')
                self.assertEqual(self.phone.values()[1], applied)
                self.ok('restore')
                self.assertEqual(self.phone.values()[1], old)

    def test_invalid_and_missing_interfaces_are_skipped(self):
        self.phone.watermark.write_text('not-a-number\n')
        self.ok('apply')
        self.assertEqual(int(self.phone.mglru.read_text().strip(), 0), 3)
        self.assertEqual(self.phone.watermark.read_text(), 'not-a-number\n')
        self.ok('restore')
        self.phone.watermark.unlink()
        self.ok('apply')
        self.ok('restore')
        self.phone.mglru.unlink()
        self.ok('apply')
        self.ok('restore')
        self.assertFalse(self.phone.mglru.exists())
        self.assertFalse(self.phone.watermark.exists())

    def test_failed_apply_write_is_reported(self):
        self.phone.watermark.chmod(0o444)
        result = self.phone.run('apply', FIXTURE_DENY_WRITE=str(self.phone.watermark))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.watermark.read_text(), '10\n')
        self.phone.watermark.chmod(0o600)
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_error_after_write_is_reported_and_target_remains_restorable(self):
        result = self.phone.run('apply', FIXTURE_FAIL_AFTER_WRITE=str(self.phone.watermark))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (3, 64))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_failed_restore_keeps_baseline_for_retry(self):
        self.ok('apply')
        self.phone.watermark.chmod(0o444)
        result = self.phone.run('restore', FIXTURE_DENY_WRITE=str(self.phone.watermark))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.watermark.read_text().strip(), '64')
        self.phone.watermark.chmod(0o600)
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_restore_error_after_verified_write_is_reported_without_stale_record(self):
        self.ok('apply')
        result = self.phone.run('restore', FIXTURE_FAIL_AFTER_WRITE=str(self.phone.watermark))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (2, 10))
        self.assertFalse((self.phone.state / 'session/watermark').exists())
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_restore_rejects_unknown_state_format_without_writing(self):
        self.ok('apply')
        record = self.phone.state / 'session/format'
        record.write_text('999\n')
        result = self.phone.run('restore')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (3, 64))
        record.write_text('1\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_toggle_pause_survives_boot_and_can_be_reactivated(self):
        self.ok('apply')
        self.ok('toggle')
        self.assertEqual(self.phone.values(), (2, 10))
        self.ok('boot')
        self.assertEqual(self.phone.values(), (2, 10))
        self.phone.boot_id.write_text('00000000-0000-4000-8000-000000000002\n')
        self.phone.mglru.write_text('4\n')
        self.phone.watermark.write_text('1\n')
        self.ok('boot')
        self.assertEqual(self.phone.values(), (4, 1))
        self.ok('toggle')
        self.assertEqual(self.phone.values(), (5, 64))

    def test_pause_persistence_and_resume_removal_fail_closed(self):
        self.ok('apply')
        paused = self.phone.state / 'paused'
        paused.mkdir()
        # A directory cannot be opened as the persistent pause marker.
        result = self.phone.run('toggle')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (3, 64))
        self.assertNotIn('Perfil pausado;', result.stdout)
        self.assertTrue(paused.is_dir())
        paused.rmdir()
        self.ok('toggle')
        self.assertEqual(self.phone.values(), (2, 10))
        self.assertTrue(paused.is_file())
        self.phone.stub('rm', r'''for arg in "$@"; do
  if [ "$arg" = "$FIXTURE_PAUSED_PATH" ]; then exit 1; fi
done
exec /usr/bin/rm "$@"''')
        result = self.phone.run('toggle', FIXTURE_PAUSED_PATH=str(paused))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (2, 10))
        self.assertTrue(paused.is_file())
        self.assertNotIn('Revision terminada.', result.stdout)
        self.phone.assert_sentinels(self)

    def test_boot_respects_module_disable_and_remove(self):
        for marker in ('disable', 'remove'):
            with self.subTest(marker=marker):
                flag = self.phone.module / marker
                flag.touch()
                self.ok('boot')
                self.assertEqual(self.phone.values(), (2, 10))
                flag.unlink()

    def test_boot_wait_is_finite_and_no_apply_before_completion(self):
        result = self.phone.run('boot', FIXTURE_BOOT_COMPLETE='0')
        self.assertEqual(self.phone.values(), (2, 10))
        sleep_log = Path(self.phone.environment['FIXTURE_SLEEP_LOG'])
        if sleep_log.exists():
            self.assertLessEqual(len(sleep_log.read_text().splitlines()), 1000)
        self.phone.assert_sentinels(self)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_status_and_report_do_not_tune_the_phone(self):
        self.ok('status')
        self.ok('report')
        self.assertEqual(self.phone.values(), (2, 10))

    def test_uninstall_restores_only_owned_values(self):
        self.ok('apply')
        self.phone.watermark.write_text('128\n')
        self.ok('uninstall')
        self.assertEqual(self.phone.values(), (2, 128))

    def test_unsupported_device_platform_and_nonroot_do_not_write(self):
        for changes in ({'FIXTURE_DEVICE': 'ruby'}, {'FIXTURE_SDK': '34'},
                        {'FIXTURE_MACHINE': 'x86_64'}, {'FIXTURE_RELEASE': '6.6.1-test'},
                        {'FIXTURE_UID': '1001'}):
            with self.subTest(changes=changes):
                result = self.phone.run('apply', **changes)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.phone.values(), (2, 10))
                self.phone.assert_sentinels(self)

    def test_interrupted_same_boot_lock_requires_reboot(self):
        self.ok('status')
        boot = self.phone.boot_id.read_text().strip()
        lock = self.phone.state / ('lock.' + boot)
        lock.mkdir()
        (lock / 'pid').write_text('99999999\n')
        result = self.phone.run('apply')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (2, 10))
        self.assertTrue(lock.exists())
        self.phone.boot_id.write_text('00000000-0000-4000-8000-000000000002\n')
        self.ok('apply')
        self.assertEqual(self.phone.values(), (3, 64))

    def test_concurrent_apply_is_serialized_without_losing_baseline(self):
        child = self.phone.start('apply', FIXTURE_BLOCK_CAT=str(self.phone.mglru))
        def stop_child():
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)
        self.addCleanup(stop_child)
        reached = Path(self.phone.environment['FIXTURE_CAT_REACHED'])
        release = Path(self.phone.environment['FIXTURE_CAT_RELEASE'])
        deadline = time.monotonic() + 5
        while not reached.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(reached.exists(), 'First apply did not reach the fixture barrier')
        second = self.phone.run('apply')
        self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
        release.touch()
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stdout + stderr)
        self.assertEqual(self.phone.values(), (3, 64))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (2, 10))


if __name__ == '__main__':
    unittest.main()
