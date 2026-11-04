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
            'proc/net/dev': 'Inter-| Receive | Transmit\n wlan0: 100 1 0 0 0 0 0 0 200 2 0 0 0 0 0 0\n rmnet_data0: 300 3 0 0 0 0 0 0 400 4 0 0 0 0 0 0\n',
            'proc/modules': 'qrtr 100000 4 - Live 0xffff01234567\nicnss2 200000 3 - Live 0xffff12345678\nunrelated_private_module 3000 2 - Live 0xffff23456789\n',
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
            'settings': 'case "$3" in wifi_on) printf "0\\n";; mobile_data) printf "1\\n";; *) printf "0\\n";; esac',
            'ps': 'printf "PID STAT %%CPU TIME NAME\\n10 S 3 00:00:10 fixture.app\\n"',
            'dmesg': 'printf "[100.0] PM: suspend entry (deep)\\n[100.1] fixture unrelated secret\\n"',
            'dumpsys': '''case "$1" in
power) printf "SECRET_POWER_OTHER_SECTION\\nmWakefulness=Awake\\nmHoldingWakeLockSuspendBlocker=true\\nWake Locks: size=1\\n  PARTIAL_WAKE_LOCK fixture_tag uid=1000\\n\\nSECRET_POWER_TAIL\\n";;
suspend_control_internal) printf "Suspend stats: success=12 fail=2\\nfixture_wakeup totalTime=500\\n";;
deviceidle) printf "  mState=ACTIVE\\n  mLightState=INACTIVE\\n  SECRET_IDLE_WHITELIST\\n";;
media_projection) printf "MEDIA PROJECTION MANAGER (dumpsys media_projection)\\nMedia Projection: \\n(fixture.caster, uid=10042): TYPE_SCREEN_CAPTURE\\nPRIVATE_PROJECTION_TOKEN\\n";;
display) printf "  mWifiDisplayOn=true\\n  PRIVATE_DISPLAY_NAME_MAC\\n";;
batterystats) [ "$2" = --charged ] || exit 99
printf "  Time on battery: 10m realtime, 5m uptime\\n  Screen on: 1m\\n  SECRET_BATTERY_APP_CONTENT\\n  u0a42:\\n    TOTAL wake: 1m 2s 3ms actual partial, 4s actual background partial realtime\\n    Apk fixture.app:\\n      Wakeup alarm PRIVATE_ALARM_TAG:https://private.example/account: 7 times\\n      Wakeup alarm PRIVATE_SECOND_ALARM: 2 times\\n    Apk private@email.invalid:\\n      Wakeup alarm PRIVATE_INVALID_PACKAGE_ALARM: 100 times\\n  baduid:\\n    TOTAL wake: 100m actual partial realtime\\n";;
esac''',
            'sleep': 'printf "FORBIDDEN sleep\\n" >&2; exit 99',
        }
        for name, body in commands.items():
            p = self.put('bin/' + name, '#!/bin/sh\n' + body + '\n')
            p.chmod(0o755)
        source = (ROOT / 'scripts/chatgpt-suspend-logs.sh').read_text()
        source = source.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin', f'PATH={self.bins}:/usr/bin:/bin')
        prefixes = [('/data/adb/', 'data/adb/'), ('/sdcard/Download', 'Download'), ('/proc/', 'proc/'), ('/sys/', 'sys/'),
                    ('/vendor_dlkm/lib/modules', 'vendor_dlkm/lib/modules'), ('/vendor/lib/modules', 'vendor/lib/modules'),
                    ('/system_dlkm/lib/modules', 'system_dlkm/lib/modules'), ('/system/lib/modules', 'system/lib/modules')]
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

    def bluetooth_fixture(self,p):
        uart=p.root/'sys/bus/platform/devices/4a8c000.qcom,qup_uart'
        driver=p.root/'sys/bus/platform/drivers/msm_geni_serial'
        module=p.root/'sys/module/msm_geni_serial'
        node=p.root/'sys/firmware/devicetree/base/soc/uart@4a8c000'
        for d in (uart,driver,module,node): d.mkdir(parents=True,exist_ok=True)
        (uart/'driver').symlink_to(driver)
        (driver/'module').symlink_to(module)
        (uart/'of_node').symlink_to(node)
        tty=p.root/'sys/class/tty/ttyHS0';tty.mkdir(parents=True)
        (tty/'device').symlink_to(uart)
        p.put('sys/firmware/devicetree/base/aliases/hsuart0','/soc/uart@4a8c000\0')
        p.put('sys/firmware/devicetree/base/soc/uart@4a8c000/compatible','qcom,msm-geni-serial-hs\0')
        for field,value in {'runtime_status':'active','control':'auto','runtime_active_time':'1000','runtime_suspended_time':'200','autosuspend_delay_ms':'150','runtime_usage':'1','wakeup':'enabled','wakeup_active':'1','wakeup_active_count':'2','wakeup_total_time_ms':'1000'}.items():
            p.put('sys/bus/platform/devices/4a8c000.qcom,qup_uart/power/'+field,value+'\n')
        for field,value in {'version':'fixture-v1','srcversion':'ABCDEF012345','taint':''}.items():
            p.put('sys/module/msm_geni_serial/'+field,value+'\n')
        p.put('vendor_dlkm/lib/modules/msm_geni_serial.ko','FIXTURE_MODULE_BYTES\n')
        p.put('bin/settings','#!/bin/sh\ncase "$3" in bluetooth_on) printf "1\\n";; *) printf "0\\n";; esac\n').chmod(0o755)
        p.put('bin/ps','#!/bin/sh\nif [ "$3" = PID,NAME ]; then printf "PID NAME\\n250 vendor.qti.bluetooth@1.0-service\\n251 unrelated.app\\n"; else printf "PID STAT %%CPU TIME NAME\\n250 S 1 00:00:02 vendor.qti.bluetooth@1.0-service\\n"; fi\n').chmod(0o755)
        for pid in ('250','251'):
            fd=p.root/f'proc/{pid}/fd';fd.mkdir(parents=True)
            (fd/'0').symlink_to('/dev/ttyHS0')
            (fd/'1').symlink_to('/sdcard/PRIVATE_PHOTO_OR_PEER_DATA')
            p.put(f'proc/{pid}/cmdline','PRIVATE_PROCESS_ARGUMENTS\0PRIVATE_ACCOUNT\0')
        return uart,driver,module,node

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
        for expected in ('440', '-307000', 'fixture_wakeup', 'success=12 fail=2', 'mWakefulness=Awake', 'fixture_tag', 'Time on battery:', 'Screen on:', 'APPLIED policy0', '6.90', '(fixture.caster, uid=10042): TYPE_SCREEN_CAPTURE', 'mWifiDisplayOn=true', 'uid_wakelock u0a42 1m 2s 3ms actual partial', 'uid_package u0a42 fixture.app', 'uid_wakeup_alarm_count u0a42 fixture.app 9', 'wifi_on: 0', 'mobile_data: 1', 'wlan0 rx_bytes 100 tx_bytes 200', 'rmnet_data0 rx_bytes 300 tx_bytes 400', 'qrtr 100000 4', 'icnss2 200000 3'):
            self.assertIn(expected, report)
        for private in ('PRIVATE_TIMER_ADDRESS_OWNER', 'PRIVATE_OTHER_MODULE', 'SECRET_POWER_OTHER_SECTION', 'SECRET_POWER_TAIL', 'SECRET_IDLE_WHITELIST', 'SECRET_BATTERY_APP_CONTENT', 'PRIVATE_PROJECTION_TOKEN', 'PRIVATE_DISPLAY_NAME_MAC', 'PRIVATE_ALARM_TAG', 'PRIVATE_SECOND_ALARM', 'PRIVATE_INVALID_PACKAGE_ALARM', 'private@email.invalid', '100m actual partial', '0xffff', 'unrelated_private_module', 'boot-A', 'FORBIDDEN sleep'):
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

    def test_userspace_remains_visible_after_many_kernel_threads(self):
        p = self.phone()
        p.put('bin/ps', '#!/bin/sh\nprintf "PID STAT %%CPU TIME NAME\\n"\ni=1\nwhile [ "$i" -le 450 ]; do printf "%s I 0 00:00:00 [kworker/fixture]\\n" "$i"; i=$((i+1)); done\nprintf "5000 S 2 00:00:10 fixture.background.app\\n"\n').chmod(0o755)
        p.run()
        p.advance()
        p.run()
        report=p.report()
        self.assertIn('fixture.background.app',report)
        self.assertNotIn('[kworker/fixture]',report)

    def test_unrecognized_uid_totals_are_not_exported_as_valid_accounting(self):
        p=self.phone()
        p.put('bin/dumpsys', '#!/bin/sh\nif [ "$1" = batterystats ]; then printf "  u0a42:\\n    TOTAL wake: PRIVATE_ACCOUNT_TEXT\\n    Apk bad@email.invalid:\\n      Wakeup alarm PRIVATE_ALARM: 500 times\\n"; fi\n').chmod(0o755)
        p.run()
        p.advance()
        p.run()
        report=p.report()
        for private in ('PRIVATE_ACCOUNT_TEXT','bad@email.invalid','PRIVATE_ALARM'):
            self.assertNotIn(private,report)
        self.assertNotIn('uid_wakelock u0a42',report)
        self.assertNotIn('uid_wakeup_alarm_count u0a42',report)

    def test_missing_network_readers_report_na_not_connected_or_disconnected(self):
        p=self.phone()
        p.put('bin/settings','#!/bin/sh\nprintf "PRIVATE_OR_UNKNOWN_SETTING\\n"\n').chmod(0o755)
        (p.root/'proc/net/dev').unlink()
        (p.root/'proc/modules').unlink()
        p.run()
        p.advance()
        p.run()
        report=p.report()
        self.assertIn('wifi_on: NA',report)
        self.assertIn('mobile_data: NA',report)
        self.assertIn('NA: matching interface counters unavailable',report)
        self.assertIn('NA: matching module rows unavailable',report)
        self.assertIn('NA: no named Bluetooth candidates observed; owner unknown',report)
        self.assertNotIn('PRIVATE_OR_UNKNOWN_SETTING',report)

    def test_freezer_summary_survives_later_pm_message_flood(self):
        p=self.phone()
        body='#!/bin/sh\nprintf "[100.0] Freezing of tasks aborted after 0.015 seconds\\n[101.0] Freezing of tasks failed after 0.500 seconds (1 tasks refusing to freeze, wq_busy=0):\\n"\ni=1\nwhile [ "$i" -le 120 ]; do printf "[102.0] PM: suspend entry (s2idle)\\n[102.1] PM: suspend exit\\n[102.2] Abort: Last active Wakeup Source: qrtr_ws\\n"; i=$((i+1)); done\n'
        p.put('bin/dmesg',body).chmod(0o755)
        p.run()
        p.advance()
        p.run()
        report=p.report()
        self.assertIn('Freezing of tasks aborted after 0.015 seconds',report)
        self.assertIn('Freezing of tasks failed after 0.500 seconds',report)

    def test_uid_accounting_absence_is_explicit_without_using_checkin(self):
        p=self.phone()
        p.put('bin/dumpsys','#!/bin/sh\nif [ "$1" = batterystats ]; then [ "$2" = --charged ] || exit 99; printf "Unknown battery format\\n"; fi\n').chmod(0o755)
        p.run()
        p.advance()
        p.run()
        self.assertIn('NA: UID accounting format unavailable; no zero usage inferred',p.report())

    def test_bluetooth_runtime_mapping_hash_and_selected_descriptor_owners(self):
        import hashlib
        p=self.phone();uart,driver,module,node=self.bluetooth_fixture(p)
        originals={f:f.read_bytes() for top in ('sys','proc','vendor_dlkm') for f in (p.root/top).rglob('*') if f.is_file() and not f.is_symlink()}
        p.run('start')
        for f,before in originals.items(): self.assertEqual(f.read_bytes(),before,str(f))
        p.put('sys/bus/platform/devices/4a8c000.qcom,qup_uart/power/runtime_status','suspended\n')
        p.put('sys/bus/platform/devices/4a8c000.qcom,qup_uart/power/runtime_usage','0\n')
        p.put('bin/settings','#!/bin/sh\nprintf "0\\n"\n').chmod(0o755)
        (p.root/'proc/250/fd/0').unlink()
        p.advance()
        updated={f:f.read_bytes() for f in originals}
        p.run('finish')
        for f,before in updated.items(): self.assertEqual(f.read_bytes(),before,str(f))
        report=p.report()
        for expected in ('bluetooth_on: 1','bluetooth_on: 0','runtime_status: active','runtime_status: suspended','control: auto','qcom,msm-geni-serial-hs','DT qcom,auto-suspend-disable: absent','ABCDEF012345','TTY owner candidate: 250 vendor.qti.bluetooth@1.0-service /dev/ttyHS0','No TTY descriptor observed: 250','Candidate module SHA256'):
            self.assertIn(expected,report)
        self.assertIn(hashlib.sha256(b'FIXTURE_MODULE_BYTES\n').hexdigest(),report)
        for private in ('PRIVATE_PHOTO_OR_PEER_DATA','PRIVATE_PROCESS_ARGUMENTS','PRIVATE_ACCOUNT','TTY owner candidate: 251'):
            self.assertNotIn(private,report)

    def test_uart_error_and_zero_length_dt_boolean_are_reported_without_tuning(self):
        p=self.phone();uart,driver,module,node=self.bluetooth_fixture(p)
        p.put('sys/bus/platform/devices/4a8c000.qcom,qup_uart/power/runtime_status','error\n')
        p.put('sys/bus/platform/devices/4a8c000.qcom,qup_uart/power/control','on\n')
        (node/'qcom,auto-suspend-disable').write_bytes(b'')
        p.run();p.advance();p.run()
        report=p.report()
        self.assertIn('runtime_status: error',report)
        self.assertIn('control: on',report)
        self.assertIn('DT qcom,auto-suspend-disable: present',report)
        self.assertEqual((uart/'power/control').read_text(),'on\n')
        self.assertEqual((uart/'power/runtime_status').read_text(),'error\n')
        self.assertEqual((node/'qcom,auto-suspend-disable').read_bytes(),b'')

    def test_missing_module_mapping_is_na_not_a_fabricated_module(self):
        p=self.phone();uart,driver,module,node=self.bluetooth_fixture(p)
        (driver/'module').unlink()
        p.run();p.advance();p.run()
        report=p.report()
        self.assertIn(str(uart/'driver/module')+': NA',report)
        self.assertNotIn('Candidate module SHA256',report)

    def test_bluetooth_property_allowlist_never_requests_name_address_or_all_properties(self):
        p=self.phone()
        log=p.root/'property-calls'
        body='#!/bin/sh\nprintf "%s\\n" "${1:-ALL_PROPERTIES}" >> "'+str(log)+'"\ncase "$1" in persist.vendor.service.bdroid.sibs) printf "false\\n";; ro.vendor.build.fingerprint) printf "vendor/tapas/fixture:13/release-keys\\n";; ""|*.address|*.bdaddr|*.name|ro.serialno) printf "PRIVATE_BT_PEER AA:BB:CC:DD:EE:FF\\n";; *) :;; esac\n'
        p.put('bin/getprop',body).chmod(0o755)
        p.run();p.advance();p.run()
        report=p.report();calls=log.read_text().splitlines()
        self.assertIn('persist.vendor.service.bdroid.sibs: false',report)
        self.assertIn('vendor/tapas/fixture:13/release-keys',report)
        self.assertNotIn('PRIVATE_BT_PEER',report)
        self.assertNotIn('AA:BB:CC:DD:EE:FF',report)
        self.assertNotIn('ALL_PROPERTIES',calls)
        self.assertFalse(any('bdaddr' in key or 'address' in key or key.endswith('.name') for key in calls))

    def test_unavailable_bluetooth_candidate_reader_is_not_reported_as_port_closed(self):
        p=self.phone()
        p.put('bin/ps','#!/bin/sh\nif [ "$3" = PID,NAME ]; then exit 1; fi\nprintf "PID STAT %%CPU TIME NAME\\n"\n').chmod(0o755)
        p.run();p.advance();p.run()
        report=p.report()
        self.assertIn('NA: candidate process reader unavailable',report)
        self.assertIn('TTY candidate probe exit status: 1',report)
        self.assertNotIn('No TTY descriptor observed:',report)

    def test_uart_device_is_never_opened_to_collect_metadata(self):
        p=self.phone();self.bluetooth_fixture(p)
        p.put('bin/cat','#!/bin/sh\ncase "$1" in /dev/ttyHS*) printf "FORBIDDEN_UART_READ\\n"; exit 99;; esac\nexec /bin/cat "$@"\n').chmod(0o755)
        p.run();p.advance();p.run()
        self.assertNotIn('FORBIDDEN_UART_READ',p.report())
        self.assertIn('TTY owner candidate:',p.report())

    def test_bluetooth_manager_scanners_are_scoped_and_peer_data_is_filtered(self):
        p=self.phone()
        data='Bluetooth Status\n  enabled: true\n  state: ON\n  address: AA:BB:CC:DD:EE:FF\n  name: PRIVATE_PHONE_NAME\n\nGATT Scanner Map\n  fixture.scanner (Registered)\n  LE scans (started/stopped)                                  : 4 / 3\n  Scan time in ms (active/suspend/total)                      : 100 / 20 / 120\n  Ongoing scans                                               :\n    PRIVATE_SCAN_FILTER_AND_PEER AA:BB:CC:DD:EE:FF\nGATT Advertiser Map\n  private.advertiser (Registered)\n  Ongoing scans                                               :\nGATT Client Map\n  PRIVATE_BONDED_NAME\n'
        original=(p.bins/'dumpsys').read_text()
        p.put('bin/dumpsys-base',original).chmod(0o755)
        fixture=p.put('bluetooth-manager',data)
        wrapper='#!/bin/sh\nif [ "$1" = bluetooth_manager ]; then cat "'+str(fixture)+'"; else exec "'+str(p.bins/'dumpsys-base')+'" "$@"; fi\n'
        p.put('bin/dumpsys',wrapper).chmod(0o755)
        p.run('start')
        fixture.write_text('Bluetooth Status\n  enabled: false\n  state: OFF\n  address: AA:BB:CC:DD:EE:FF\n  name: PRIVATE_PHONE_NAME\n\n')
        p.advance();p.run('finish')
        report=p.report()
        for value in ('adapter_enabled true','adapter_state ON','adapter_enabled false','adapter_state OFF','BLE scanner package fixture.scanner','BLE scan counts fixture.scanner started 4 stopped 3','BLE scan time_ms fixture.scanner active 100 suspended 20 total 120','BLE ongoing scan section observed fixture.scanner'):
            self.assertIn(value,report)
        for private in ('AA:BB:CC:DD:EE:FF','PRIVATE_PHONE_NAME','PRIVATE_SCAN_FILTER_AND_PEER','private.advertiser','PRIVATE_BONDED_NAME'):
            self.assertNotIn(private,report)

    def test_unlisted_bluetooth_manager_format_is_not_adapter_off(self):
        p=self.phone()
        p.put('bin/dumpsys','#!/bin/sh\nif [ "$1" = bluetooth_manager ]; then printf "PRIVATE_BT_UNKNOWN AA:BB:CC:DD:EE:FF\\n"; fi\n').chmod(0o755)
        p.run();p.advance();p.run()
        report=p.report()
        self.assertIn('NA: Bluetooth adapter state format unavailable',report)
        self.assertIn('NA: supported BLE scanner attribution unavailable; no absence inferred',report)
        self.assertNotIn('adapter_enabled false',report)
        self.assertNotIn('PRIVATE_BT_UNKNOWN',report)
        self.assertNotIn('AA:BB:CC:DD:EE:FF',report)

    def test_unlisted_scanner_header_clears_previous_package(self):
        p=self.phone()
        data='GATT Scanner Map\n  fixture.scanner (Registered)\n  LE scans (started/stopped) : 1 / 1\n  android.uid.system:1000 (Registered)\n  Ongoing scans :\nGATT Client Map\n'
        p.put('bin/dumpsys','#!/bin/sh\nif [ "$1" = bluetooth_manager ]; then cat <<\'EOF\'\n'+data+'EOF\nfi\n').chmod(0o755)
        p.run();p.advance();p.run()
        report=p.report()
        self.assertIn('BLE scanner package fixture.scanner',report)
        self.assertNotIn('BLE ongoing scan section observed fixture.scanner',report)
        self.assertNotIn('BLE scanner package android.uid',report)

    def test_unknown_vendor_section_cannot_export_package_like_peer_names(self):
        for header in ('Vendor Peer List:','  VendorPeerList:','  VendorPeerList'):
            with self.subTest(header=header):
                p=self.phone()
                data='GATT Scanner Map\n  fixture.scanner (Registered)\n  LE scans (started/stopped) : 1 / 1\n'+header+'\n  PRIVATE.PEER.NAME\n  Ongoing scans :\n'
                p.put('bin/dumpsys','#!/bin/sh\nif [ "$1" = bluetooth_manager ]; then cat <<\'EOF\'\n'+data+'EOF\nfi\n').chmod(0o755)
                p.run();p.advance();p.run()
                report=p.report()
                self.assertIn('BLE scanner package fixture.scanner',report)
                self.assertNotIn('PRIVATE.PEER.NAME',report)
                self.assertNotIn('BLE ongoing scan section observed fixture.scanner',report)

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
