#!/usr/bin/env python3
"""Exercise the actual finite WALT module using isolated Android fixtures.

Reuse the memory module's path-only harness. No production test hooks, real
sysfs writes, root privilege, kernel compilation, or GitHub workflow is used.
"""
from pathlib import Path
import os
import re
import subprocess
import time
import unittest
from test_fluidez_module import PhoneFixture

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'modules/chatgpt-cpu-respuesta'


class CpuPhoneFixture(PhoneFixture):
    def __init__(self):
        super().__init__()
        self.cpu_root = self.root / 'sys/devices/system/cpu/cpufreq'
        self.rates = {index: self.put(
            f'sys/devices/system/cpu/cpufreq/policy{index}/walt/up_rate_limit_us',
            str(value) + '\n') for index, value in ((0, 40000), (4, 60000))}
        self.global_rate = self.cpu_root / 'walt/up_rate_limit_us'
        for index in (0, 4):
            self.set_governor(index, 'walt')
        self.sentinels.update({
            'sys/kernel/mm/lru_gen/enabled': '0x0002\n',
            'proc/sys/vm/watermark_scale_factor': '10\n',
            'sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq': '300000\n',
            'sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq': '1900800\n',
            'sys/devices/system/cpu/cpufreq/policy4/scaling_min_freq': '300000\n',
            'sys/devices/system/cpu/cpufreq/policy4/scaling_max_freq': '2803200\n',
            'sys/devices/system/cpu/cpufreq/policy0/walt/down_rate_limit_us': '1000\n',
            'sys/devices/system/cpu/cpufreq/policy4/walt/down_rate_limit_us': '1000\n',
            'sys/devices/system/cpu/cpufreq/policy0/walt/hispeed_freq': '600000\n',
            'sys/class/kgsl/kgsl-3d0/devfreq/min_freq': '200000000\n',
            'sys/class/kgsl/kgsl-3d0/devfreq/max_freq': '950000000\n',
        })
        for name, value in self.sentinels.items():
            self.put(name, value)
        self.write_log = self.root / 'cpu-write-attempts'
        self.environment['FIXTURE_CPU_WRITE_LOG'] = str(self.write_log)
        self.stub('sh', r'''last=
for arg in "$@"; do last=$arg; done
case "${last##*/}" in up_rate_limit_us) printf '%s\n' "$last" >> "$FIXTURE_CPU_WRITE_LOG";; esac
if [ -n "$FIXTURE_DENY_WRITE" ] && [ "$last" = "$FIXTURE_DENY_WRITE" ]; then exit 1; fi
/bin/sh "$@"
result=$?
if [ "$result" -eq 0 ] && [ -n "$FIXTURE_FAIL_AFTER_WRITE" ] && [ "$last" = "$FIXTURE_FAIL_AFTER_WRITE" ]; then exit 1; fi
exit "$result"''')

    def rewrite(self, source):
        replacements = {
            '/data/adb': str(self.root / 'data/adb'),
            '/proc/': str(self.root / 'proc') + '/',
            '/sys/': str(self.root / 'sys') + '/',
            '/sdcard/Download': str(self.root / 'Download'),
            '/data/local/tmp': str(self.root / 'data/local/tmp'),
            '/system/bin/sh': '/bin/sh',
        }
        source = re.sub('|'.join(re.escape(key) for key in replacements),
                        lambda match: replacements[match.group()], source)
        fixture_path = str(self.bins) + ':/usr/bin:/bin'
        return re.sub(r'(?m)^(export )?PATH=.*$',
                      'PATH=' + fixture_path + '\nexport PATH', source)

    def install_control(self, upgrade=False):
        self.state = self.root / 'data/adb/chatgpt-cpu-respuesta'
        name = 'chatgpt_cpu_respuesta-upgraded' if upgrade else 'chatgpt_cpu_respuesta'
        self.module = self.root / 'data/adb/modules' / name
        self.script = self.module / 'bin/control.sh'
        self.script.parent.mkdir(parents=True, exist_ok=True)
        self.script.write_text(self.rewrite((PROJECT / 'bin/control.sh').read_text()))
        self.script.chmod(0o755)
        self.action = self.module / 'action.sh'
        self.action.write_text(self.rewrite((PROJECT / 'action.sh').read_text()))
        self.action.chmod(0o755)
        (self.module / 'module.prop').write_text('id=chatgpt_cpu_respuesta\nname=Fixture\nversion=fixture\n')
        # Test the real action wrapper with a harmless, argument-recording collector.
        collector = self.module / 'bin/collect.sh'
        collector.write_text('''#!/bin/sh
printf '%s\\n' "$#" "$@" > "$FIXTURE_ROOT/collector-arguments"
printf 'FIXTURE COLLECTOR\\n'
exit 23
''')
        collector.chmod(0o755)

    def set_governor(self, index, name):
        relative = f'sys/devices/system/cpu/cpufreq/policy{index}/scaling_governor'
        self.sentinels[relative] = name + '\n'
        self.put(relative, name + '\n')

    def values(self):
        return tuple(int(self.rates[index].read_text().strip()) for index in (0, 4))

    def writes(self):
        return self.write_log.read_text().splitlines() if self.write_log.exists() else []

    def make_global(self, value=50000, *, aliases=False):
        self.global_rate.parent.mkdir(parents=True, exist_ok=True)
        self.global_rate.write_text(str(value) + '\n')
        for path in self.rates.values():
            path.unlink()
            if aliases:
                path.symlink_to(self.global_rate)

    def run_action(self):
        return subprocess.run(['/bin/sh', str(self.action)], env=self.environment,
                              capture_output=True, text=True, timeout=8)


class CpuRespuestaModuleTests(unittest.TestCase):
    def setUp(self):
        self.phone = CpuPhoneFixture()
        self.addCleanup(self.phone.close)

    def ok(self, action, **changes):
        result = self.phone.run(action, **changes)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.phone.assert_sentinels(self)
        return result

    def test_apply_restore_idempotence_upgrade_and_private_baseline(self):
        self.ok('apply')
        self.assertEqual(self.phone.values(), (30000, 45000))
        self.assertFalse(self.phone.state.is_relative_to(self.phone.module))
        self.assertEqual(self.phone.state.stat().st_mode & 0o777, 0o700)
        self.ok('apply')
        self.phone.install_control(upgrade=True)
        self.ok('apply')
        self.assertEqual(self.phone.values(), (30000, 45000))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))

    def test_only_slow_supported_rates_are_reduced_with_ceiling(self):
        self.phone.rates[4].write_text('20000\n')
        for raw, expected in (('0', 0), ('1', 1), ('20000', 20000),
                              ('20001', 15001), ('33333', 25000),
                              ('40000', 30000), ('99999', 75000),
                              ('100000', 75000), ('100001', 100001)):
            with self.subTest(rate=raw):
                self.phone.rates[0].write_text(raw + '\n')
                self.ok('apply')
                self.assertEqual(self.phone.values(), (expected, 20000))
                self.ok('restore')
                self.assertEqual(self.phone.values(), (int(raw), 20000))

    def test_invalid_or_missing_rates_are_not_written(self):
        self.phone.rates[4].write_text('20000\n')
        for raw in ('invalid', '-1', '4294967296', '0x100000000'):
            with self.subTest(rate=raw):
                self.phone.rates[0].write_text(raw + '\n')
                before = len(self.phone.writes())
                self.ok('apply')
                self.assertEqual(self.phone.rates[0].read_text(), raw + '\n')
                self.assertEqual(len(self.phone.writes()), before)
                self.ok('restore')
        self.phone.rates[0].unlink()
        self.phone.rates[4].unlink()
        self.ok('apply')
        self.ok('restore')
        self.assertFalse(self.phone.rates[0].exists())
        self.assertFalse(self.phone.rates[4].exists())

    def test_global_scope_when_both_policy_nodes_are_absent(self):
        self.phone.make_global()
        self.ok('apply')
        self.assertEqual(self.phone.global_rate.read_text().strip(), '37500')
        self.assertEqual(len(self.phone.writes()), 1)
        self.ok('restore')
        self.assertEqual(self.phone.global_rate.read_text().strip(), '50000')

    def test_global_scope_deduplicates_policy_symlinks_to_global(self):
        self.phone.make_global(50000, aliases=True)
        self.ok('apply')
        self.assertEqual(self.phone.values(), (37500, 37500))
        self.assertEqual(len(self.phone.writes()), 1)
        self.ok('restore')
        self.assertEqual(self.phone.values(), (50000, 50000))

    def test_policy_symlink_and_hardlink_aliases_are_written_once(self):
        shared = self.phone.put('sys/shared-walt/up_rate_limit_us', '40000\n')
        for path in self.phone.rates.values():
            path.unlink()
            path.symlink_to(shared)
        self.ok('apply')
        self.assertEqual(self.phone.values(), (30000, 30000))
        self.assertEqual(len(self.phone.writes()), 1)
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 40000))
        for path in self.phone.rates.values():
            path.unlink()
        self.phone.rates[0].write_text('40000\n')
        os.link(self.phone.rates[0], self.phone.rates[4])
        before = len(self.phone.writes())
        self.ok('apply')
        self.assertEqual(self.phone.values(), (30000, 30000))
        self.assertEqual(len(self.phone.writes()) - before, 1)
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 40000))

    def test_shared_policy_alias_restore_requires_both_governors_unchanged(self):
        shared = self.phone.put('sys/shared-walt/up_rate_limit_us', '40000\n')
        for path in self.phone.rates.values():
            path.unlink()
            path.symlink_to(shared)
        self.ok('apply')
        self.assertEqual(self.phone.values(), (30000, 30000))
        before = len(self.phone.writes())
        self.phone.set_governor(4, 'schedutil')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (30000, 30000))
        self.assertEqual(len(self.phone.writes()), before)

    def test_plan_is_captured_before_writes_and_preserves_later_policy_change(self):
        self.phone.stub('sh', r'''last=
for arg in "$@"; do last=$arg; done
if [ "$last" = "$FIXTURE_TRIGGER_NODE" ] && [ ! -e "$FIXTURE_CHANGE_DONE" ]; then
  printf '80000' > "$FIXTURE_MUTATE_NODE"
  : > "$FIXTURE_CHANGE_DONE"
fi
exec /bin/sh "$@"''')
        self.ok('apply', FIXTURE_TRIGGER_NODE=str(self.phone.rates[0]),
                FIXTURE_MUTATE_NODE=str(self.phone.rates[4]),
                FIXTURE_CHANGE_DONE=str(self.phone.root / 'third-party-change'))
        self.assertEqual(self.phone.values(), (30000, 80000))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 80000))

    def test_unreadable_existing_nonparticipant_alias_vetoes_all_writes(self):
        self.phone.rates[4].unlink()
        self.phone.rates[4].symlink_to(self.phone.rates[0])
        self.phone.set_governor(4, 'schedutil')
        self.phone.stub('readlink', r'''last=
for arg in "$@"; do last=$arg; done
if [ "$last" = "$FIXTURE_DENY_IDENTITY" ]; then exit 1; fi
exec /usr/bin/readlink "$@"''')
        self.ok('apply', FIXTURE_DENY_IDENTITY=str(self.phone.rates[4]))
        self.assertEqual(self.phone.values(), (40000, 40000))
        self.assertEqual(self.phone.writes(), [])
        self.ok('restore', FIXTURE_DENY_IDENTITY=str(self.phone.rates[4]))
        self.assertEqual(self.phone.values(), (40000, 40000))
        self.assertEqual(self.phone.writes(), [])

    def test_unknown_policy8_vetoes_apply_and_previously_identified_restore(self):
        rate8 = self.phone.put('sys/devices/system/cpu/cpufreq/policy8/walt/up_rate_limit_us', '80000\n')
        governor8 = self.phone.put('sys/devices/system/cpu/cpufreq/policy8/scaling_governor', 'walt\n')
        self.ok('apply')
        self.assertEqual(self.phone.values(), (40000, 60000))
        self.assertEqual(rate8.read_text(), '80000\n')
        self.assertEqual(self.phone.writes(), [])
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))
        # Capture a valid plan first, then introduce the unknown scope before restore.
        rate8.unlink()
        governor8.unlink()
        rate8.parent.rmdir()
        governor8.parent.rmdir()
        self.ok('apply')
        self.assertEqual(self.phone.values(), (30000, 45000))
        before = len(self.phone.writes())
        self.phone.put('sys/devices/system/cpu/cpufreq/policy8/walt/up_rate_limit_us', '80000\n')
        self.phone.put('sys/devices/system/cpu/cpufreq/policy8/scaling_governor', 'walt\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (30000, 45000))
        self.assertEqual(rate8.read_text(), '80000\n')
        self.assertEqual(governor8.read_text(), 'walt\n')
        self.assertEqual(len(self.phone.writes()), before)

    def test_global_and_independent_policy_scopes_are_not_mixed(self):
        self.phone.global_rate.parent.mkdir(parents=True)
        self.phone.global_rate.write_text('50000\n')
        self.phone.rates[4].unlink()
        self.ok('apply')
        self.assertEqual(self.phone.global_rate.read_text(), '50000\n')
        self.assertNotIn(str(self.phone.global_rate), self.phone.writes())
        self.ok('restore')
        self.assertEqual(self.phone.rates[0].read_text().strip(), '40000')

    def test_global_scope_is_skipped_when_one_governor_is_not_walt(self):
        self.phone.make_global()
        self.phone.set_governor(4, 'schedutil')
        self.ok('apply')
        self.assertEqual(self.phone.global_rate.read_text(), '50000\n')
        self.assertEqual(self.phone.writes(), [])

    def test_third_party_change_is_preserved_on_apply_and_restore(self):
        self.ok('apply')
        self.phone.rates[0].write_text('35000\n')
        self.ok('apply')
        self.assertEqual(self.phone.values(), (35000, 45000))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (35000, 60000))

    def test_changed_governor_prevents_restoring_that_policy(self):
        self.ok('apply')
        self.phone.set_governor(4, 'schedutil')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 45000))

    def test_changed_inode_identity_is_preserved_despite_same_path_and_value(self):
        self.ok('apply')
        path = self.phone.rates[0]
        old = path.stat()
        replacement = self.phone.put('replacement-rate', '30000\n')
        os.replace(replacement, path)
        new = path.stat()
        self.assertNotEqual((old.st_dev, old.st_ino), (new.st_dev, new.st_ino))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (30000, 60000))

    def test_changed_canonical_alias_is_preserved(self):
        self.ok('apply')
        replacement = self.phone.put('sys/another-walt/up_rate_limit_us', '30000\n')
        self.phone.rates[0].unlink()
        self.phone.rates[0].symlink_to(replacement)
        self.ok('restore')
        self.assertEqual(self.phone.values(), (30000, 60000))

    def test_reboot_discards_old_baseline_before_any_new_apply(self):
        self.ok('apply')
        self.phone.boot_id.write_text('00000000-0000-4000-8000-000000000002\n')
        self.phone.rates[0].write_text('50000\n')
        self.phone.rates[4].write_text('80000\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (50000, 80000))
        self.ok('apply')
        self.assertEqual(self.phone.values(), (37500, 60000))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (50000, 80000))

    def test_failed_write_and_error_after_write_are_reported(self):
        path = self.phone.rates[4]
        result = self.phone.run('apply', FIXTURE_DENY_WRITE=str(path))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_text(), '60000\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))
        result = self.phone.run('apply', FIXTURE_FAIL_AFTER_WRITE=str(path))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (30000, 45000))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))

    def test_failed_restore_retains_record_for_retry(self):
        self.ok('apply')
        path = self.phone.rates[4]
        result = self.phone.run('restore', FIXTURE_DENY_WRITE=str(path))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_text().strip(), '45000')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))

    def test_restore_rejects_unknown_journal_format_without_write(self):
        self.ok('apply')
        format_file = self.phone.state / 'session/format'
        format_file.write_text('999\n')
        result = self.phone.run('restore')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (30000, 45000))
        format_file.write_text('1\n')
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))

    def test_pause_persistence_failures_precede_control_changes(self):
        self.ok('apply')
        paused = self.phone.state / 'paused'
        paused.mkdir()
        result = self.phone.run('toggle')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (30000, 45000))
        paused.rmdir()
        self.ok('toggle')
        self.assertEqual(self.phone.values(), (40000, 60000))
        self.phone.stub('rm', r'''for arg in "$@"; do
  if [ "$arg" = "$FIXTURE_PAUSED_PATH" ]; then exit 1; fi
done
exec /usr/bin/rm "$@"''')
        result = self.phone.run('toggle', FIXTURE_PAUSED_PATH=str(paused))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (40000, 60000))
        self.assertTrue(paused.is_file())

    def test_paused_boot_disable_remove_and_finite_boot_wait(self):
        self.ok('apply')
        self.ok('toggle')
        self.assertEqual(self.phone.values(), (40000, 60000))
        self.phone.boot_id.write_text('00000000-0000-4000-8000-000000000002\n')
        self.ok('boot')
        self.assertEqual(self.phone.values(), (40000, 60000))
        self.ok('toggle')
        self.assertEqual(self.phone.values(), (30000, 45000))
        self.ok('restore')
        (self.phone.state / 'paused').unlink()
        for marker in ('disable', 'remove'):
            flag = self.phone.module / marker
            flag.touch()
            self.ok('boot')
            self.assertEqual(self.phone.values(), (40000, 60000))
            flag.unlink()
        result = self.phone.run('boot', FIXTURE_BOOT_COMPLETE='0')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.phone.values(), (40000, 60000))

    def test_concurrent_apply_is_serialized(self):
        child = self.phone.start('apply', FIXTURE_BLOCK_CAT=str(self.phone.rates[0]))
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
        self.assertTrue(reached.exists(), 'First apply never reached the fixture barrier')
        second = self.phone.run('apply')
        self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
        release.touch()
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stdout + stderr)
        self.assertEqual(self.phone.values(), (30000, 45000))
        self.ok('restore')
        self.assertEqual(self.phone.values(), (40000, 60000))

    def test_action_executes_only_collector_for_180_seconds(self):
        for active in (False, True):
            with self.subTest(active=active):
                if active:
                    self.ok('apply')
                before = self.phone.values()
                result = self.phone.run_action()
                self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
                self.assertIn('FIXTURE COLLECTOR', result.stdout)
                self.assertEqual((self.phone.root / 'collector-arguments').read_text().splitlines(), ['1', '180'])
                self.assertEqual(self.phone.values(), before)
                self.phone.assert_sentinels(self)

    def test_status_report_and_uninstall_preserve_unowned_changes(self):
        self.ok('status')
        self.ok('report')
        self.assertEqual(self.phone.values(), (40000, 60000))
        self.ok('apply')
        self.phone.rates[0].write_text('35000\n')
        self.ok('uninstall')
        self.assertEqual(self.phone.values(), (35000, 60000))

    def test_unsupported_device_platform_and_nonroot_do_not_write(self):
        for changes in ({'FIXTURE_DEVICE': 'ruby'}, {'FIXTURE_SDK': '34'},
                        {'FIXTURE_MACHINE': 'x86_64'}, {'FIXTURE_RELEASE': '6.6.1-test'},
                        {'FIXTURE_UID': '1001'}):
            with self.subTest(changes=changes):
                result = self.phone.run('apply', **changes)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.phone.values(), (40000, 60000))
                self.assertEqual(self.phone.writes(), [])
                self.phone.assert_sentinels(self)


if __name__ == '__main__':
    unittest.main()
