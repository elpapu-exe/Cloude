#!/usr/bin/env python3
"""Exercise the actual two-snapshot shell collector against Android file fixtures."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phone:
    def __init__(self, directory):
        self.root = Path(directory)
        self.fixtures = {
            'proc/sys/kernel/random/boot_id': 'boot-A\n',
            'proc/uptime': '1000.00 4000.00\n',
            'proc/timer_list': 'Timer List Version: v0.9\nnow at 100000000000 nsecs\nPRIVATE_TIMER_ADDRESS_OWNER\n',
            'proc/stat': 'cpu 1 2 3 4 5 6 7 8\nprocs_running 1\nprocs_blocked 2\n',
            'proc/loadavg': '6.90 6.86 6.69 9/3174 7436\n',
            'proc/meminfo': 'MemAvailable: 900000 kB\nSwapTotal: 2097148 kB\nSwapFree: 600000 kB\n',
            'proc/vmstat': 'pgscan_direct 5\npswpin 10\npswpout 20\n',
            'proc/pressure/cpu': 'some avg10=1.00 total=100\n',
            'proc/pressure/memory': 'some avg10=2.00 total=200\nfull avg10=1.00 total=100\n',
            'sys/class/power_supply/battery/temp': '440\n',
            'sys/class/power_supply/battery/status': 'Discharging\n',
            'sys/class/power_supply/battery/current_now': '-307000\n',
            'sys/class/kgsl/kgsl-3d0/force_clk_on': '0\n',
            'sys/kernel/debug/wakeup_sources': 'name active_count event_count total_time\nfixture_wakeup 3 9 500\n',
            'sys/power/suspend_stats/success': '12\n',
            'sys/power/suspend_stats/fail': '2\n',
            'sys/kernel/wakeup_reasons/last_resume_reason': 'fixture_irq\n',
            'data/adb/chatgpt-cpu-respuesta/history.log': 'APPLIED policy0 40000->30000\n',
            'data/adb/unrelated-module/history.log': 'PRIVATE_OTHER_MODULE\n',
        }
        for path, text in self.fixtures.items():
            self.put(path, text)
        (self.root / 'data/adb').mkdir(parents=True, exist_ok=True)
        (self.root / 'Download').mkdir()
        self.bins = self.root / 'bin'
        self.bins.mkdir()
        commands = {
            'id': 'printf "0\\n"',
            'stat': 'printf "0\\n"',
            'getprop': 'printf "fixture\\n"',
            'ps': 'printf "PID STAT %%CPU TIME NAME\\n10 S 3 00:00:10 fixture.app\\n"',
            'dmesg': 'printf "[100.0] PM: suspend entry (deep)\\n[100.1] fixture unrelated secret\\n"',
            'dumpsys': '''case "$1" in
power) printf "SECRET_POWER_OTHER_SECTION\\nmWakefulness=Awake\\nmHoldingWakeLockSuspendBlocker=true\\nWake Locks: size=1\\n  PARTIAL_WAKE_LOCK fixture_tag uid=1000\\n\\nSECRET_POWER_TAIL\\n";;
suspend_control_internal) printf "Suspend stats: success=12 fail=2\\nfixture_wakeup totalTime=500\\n";;
deviceidle) printf "  mState=ACTIVE\\n  mLightState=INACTIVE\\n  SECRET_IDLE_WHITELIST\\n";;
media_projection) printf "MEDIA PROJECTION MANAGER (dumpsys media_projection)\\nMedia Projection: \\n(fixture.caster, uid=10042): TYPE_SCREEN_CAPTURE\\nPRIVATE_PROJECTION_TOKEN\\n";;
display) printf "  mWifiDisplayOn=true\\n  PRIVATE_DISPLAY_NAME_MAC\\n";;
batterystats) printf "  Time on battery: 10m realtime, 5m uptime\\n  Screen on: 1m\\n  SECRET_BATTERY_APP_CONTENT\\n";;
esac''',
            'sleep': 'printf "FORBIDDEN sleep\\n" >&2; exit 99',
        }
        for name, body in commands.items():
            p = self.put('bin/' + name, '#!/bin/sh\n' + body + '\n')
            p.chmod(0o755)
        source = (ROOT / 'scripts/chatgpt-suspend-logs.sh').read_text()
        source = source.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin', f'PATH={self.bins}:/usr/bin:/bin')
        prefixes = [('/data/adb/', 'data/adb/'), ('/sdcard/Download', 'Download'), ('/proc/', 'proc/'), ('/sys/', 'sys/')]
        # /proc/sys is one path, not a nested replacement of the /sys root.
        for i, (prefix, _) in enumerate(prefixes):
            source = source.replace(prefix, f'@@FIXTURE_ROOT_{i}@@')
        for i, (_, destination) in enumerate(prefixes):
            source = source.replace(f'@@FIXTURE_ROOT_{i}@@', str(self.root / destination) + ('/' if destination.endswith('/') else ''))
        self.script = self.put('collector.sh', source)
        self.state = self.root / 'data/adb/chatgpt-reposo-diagnostico'

    def put(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def run(self, mode='auto', ok=True):
        result = subprocess.run(['/bin/sh', str(self.script), mode], text=True, capture_output=True, timeout=12)
        if ok and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        if not ok and not result.returncode:
            raise AssertionError('Unexpected success: ' + result.stdout)
        return result

    def advance(self, *, reboot=False, mono='120000000000'):
        self.put('proc/uptime', '1600.00 4400.00\n')
        self.put('proc/timer_list', f'Timer List Version: v0.9\nnow at {mono} nsecs\nPRIVATE_TIMER_ADDRESS_OWNER\n')
        if reboot:
            self.put('proc/sys/kernel/random/boot_id', 'boot-B\n')

    def report(self):
        paths = list((self.root / 'Download').glob('ChatGPT-Reposo-*.txt'))
        assert len(paths) == 1, paths
        return paths[0].read_text()


class SuspendDiagnosticTests(unittest.TestCase):
    def phone(self):
        d = tempfile.TemporaryDirectory(prefix='suspend-phone-')
        self.addCleanup(d.cleanup)
        return Phone(d.name)

    def test_two_taps_exit_and_measure_clock_difference_without_tuning(self):
        p = self.phone()
        first = p.run()
        self.assertIn('START SAVED', first.stdout)
        self.assertFalse((p.state / 'lock').exists())
        self.assertEqual(list((p.root / 'Download').iterdir()), [])
        self.assertTrue((p.state / 'pending.txt').is_file())
        p.advance()
        before = {path: (p.root / path).read_bytes() for path in p.fixtures}
        second = p.run()
        self.assertIn('TEST FINISHED', second.stdout)
        report = p.report()
        self.assertIn('580.00 seconds (96.7% of interval)', report)
        for expected in ('440', '-307000', 'fixture_wakeup', 'success=12 fail=2', 'mWakefulness=Awake', 'fixture_tag', 'Time on battery:', 'Screen on:', 'APPLIED policy0', '6.90', '(fixture.caster, uid=10042): TYPE_SCREEN_CAPTURE', 'mWifiDisplayOn=true'):
            self.assertIn(expected, report)
        for private in ('PRIVATE_TIMER_ADDRESS_OWNER', 'PRIVATE_OTHER_MODULE', 'SECRET_POWER_OTHER_SECTION', 'SECRET_POWER_TAIL', 'SECRET_IDLE_WHITELIST', 'SECRET_BATTERY_APP_CONTENT', 'PRIVATE_PROJECTION_TOKEN', 'PRIVATE_DISPLAY_NAME_MAC', 'boot-A', 'FORBIDDEN sleep'):
            self.assertNotIn(private, report)
        self.assertFalse((p.state / 'pending.txt').exists())
        self.assertFalse((p.state / 'lock').exists())
        for path, value in before.items():
            self.assertEqual((p.root / path).read_bytes(), value, path)

    def test_missing_monotonic_and_optional_sources_do_not_fabricate_duration(self):
        p = self.phone()
        (p.root / 'proc/timer_list').unlink()
        (p.root / 'sys/kernel/debug/wakeup_sources').unlink()
        p.run('start')
        p.put('proc/uptime', '1600.00 4400.00\n')
        p.run('finish')
        report = p.report()
        self.assertIn('Monotonic clock unavailable; suspend duration not computed.', report)
        self.assertNotIn('Approximate system-suspended time:', report)
        self.assertIn('NA', report)

    def test_reboot_blocks_subtraction(self):
        p = self.phone()
        p.run()
        p.advance(reboot=True)
        p.run()
        report = p.report()
        self.assertIn('BOOT CHANGED', report)
        self.assertNotIn('Approximate system-suspended time:', report)

    def test_inconsistent_clocks_do_not_report_negative_suspend(self):
        p = self.phone()
        p.run()
        p.advance(mono='800000000000')
        p.run()
        self.assertIn('Inconsistent clock samples', p.report())
        self.assertNotIn('Approximate system-suspended time:', p.report())

    def test_duplicate_start_preserves_original_baseline(self):
        p = self.phone()
        p.run('start')
        baseline = (p.state / 'pending.txt').read_bytes()
        p.advance()
        p.run('start', ok=False)
        self.assertEqual((p.state / 'pending.txt').read_bytes(), baseline)

    def test_locked_downloads_preserve_baseline_for_retry(self):
        p = self.phone()
        p.run()
        (p.root / 'Download').rmdir()
        p.run('finish', ok=False)
        self.assertTrue((p.state / 'pending.txt').is_file())
        self.assertFalse((p.state / 'lock').exists())
        (p.root / 'Download').mkdir()
        p.advance()
        p.run('finish')
        self.assertIn('TEST FINISHED', p.report())

    def test_symlinked_private_state_is_rejected(self):
        p = self.phone()
        private = p.root / 'private'
        private.mkdir()
        p.state.symlink_to(private)
        p.run(ok=False)
        self.assertEqual(list(private.iterdir()), [])

    def test_symlinked_baseline_is_never_exported(self):
        p = self.phone()
        p.state.mkdir()
        secret = p.put('private', 'PRIVATE_SECRET\n')
        (p.state / 'pending.txt').symlink_to(secret)
        p.run(ok=False)
        self.assertEqual(secret.read_text(), 'PRIVATE_SECRET\n')
        self.assertEqual(list((p.root / 'Download').iterdir()), [])

    def test_live_lock_refuses_another_capture(self):
        p = self.phone()
        lock = p.state / 'lock'
        lock.mkdir(parents=True)
        (lock / 'pid').write_text(str(os.getpid())+'\n')
        (lock / 'boot').write_text('boot-A\n')
        p.run(ok=False)
        self.assertTrue((lock / 'pid').is_file())

    def test_previous_boot_lock_can_be_recovered_without_killing_processes(self):
        p = self.phone()
        lock = p.state / 'lock'
        lock.mkdir(parents=True)
        (lock / 'pid').write_text(str(os.getpid())+'\n')
        (lock / 'boot').write_text('boot-old\n')
        p.run('start')
        self.assertFalse(lock.exists())
        self.assertTrue((p.state / 'pending.txt').exists())

    def test_finish_without_baseline_and_invalid_mode_are_rejected(self):
        p = self.phone()
        p.run('finish', ok=False)
        p.run('force-suspend', ok=False)
        self.assertEqual(list((p.root / 'Download').iterdir()), [])

    def test_metadata_write_error_prevents_start_success_and_preserves_retry(self):
        p = self.phone()
        mock = p.put('bin/cat', '#!/bin/sh\nif [ "$1" = "' + str(p.root/'proc/uptime') + '" ]; then mkdir -p "' + str(p.state/'START.uptime') + '"; fi\nexec /bin/cat "$@"\n')
        mock.chmod(0o755)
        result = p.run('start', ok=False)
        self.assertNotIn('START SAVED', result.stdout)
        self.assertFalse((p.state/'pending.txt').exists())
        self.assertFalse((p.state/'lock').exists())
        mock.unlink()
        (p.state/'START.uptime').rmdir()
        p.run('start')
        self.assertTrue((p.state/'pending.txt').exists())

    def test_baseline_read_error_prevents_finish_and_preserves_original(self):
        p = self.phone()
        p.run()
        baseline = (p.state/'pending.txt').read_bytes()
        mock = p.put('bin/cat', '#!/bin/sh\nif [ "$1" = "' + str(p.state/'pending.txt') + '" ]; then exit 1; fi\nexec /bin/cat "$@"\n')
        mock.chmod(0o755)
        result = p.run('finish', ok=False)
        self.assertNotIn('TEST FINISHED', result.stdout)
        self.assertEqual((p.state/'pending.txt').read_bytes(), baseline)
        self.assertNotIn('TEST FINISHED', p.report())

    def test_end_metadata_write_error_preserves_baseline_without_success_marker(self):
        p = self.phone()
        p.run()
        baseline = (p.state/'pending.txt').read_bytes()
        mock = p.put('bin/cat', '#!/bin/sh\nif [ "$1" = "' + str(p.root/'proc/uptime') + '" ]; then mkdir -p "' + str(p.state/'END.mono') + '"; fi\nexec /bin/cat "$@"\n')
        mock.chmod(0o755)
        p.run('finish', ok=False)
        self.assertEqual((p.state/'pending.txt').read_bytes(), baseline)
        self.assertNotIn('TEST FINISHED', p.report())

    def test_unknown_projection_format_is_unavailable_not_inactive(self):
        p = self.phone()
        p.put('bin/dumpsys', '#!/bin/sh\nif [ "$1" = media_projection ]; then printf "PRIVATE_OR_UNRECOGNIZED_PROJECTION\\n"; fi\n').chmod(0o755)
        p.run()
        p.advance()
        p.run()
        report = p.report()
        self.assertIn('NA: service unavailable or unrecognized format; no absence inferred.', report)
        self.assertNotIn('PRIVATE_OR_UNRECOGNIZED_PROJECTION', report)

    def test_module_action_contract_and_no_boot_service(self):
        module = ROOT / 'modules/chatgpt-reposo-diagnostico'
        if module.exists():
            action = (module / 'action.sh').read_text()
            self.assertIn('auto', action)
            self.assertIn('exec', action)
            for name in ('service.sh','post-fs-data.sh','system.prop'):
                self.assertFalse((module/name).exists())


if __name__ == '__main__':
    unittest.main()
