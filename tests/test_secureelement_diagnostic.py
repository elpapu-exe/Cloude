#!/usr/bin/env python3
"""Exercise the SecureElement report with Android fixtures, without a phone."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SE_STACK = '"main" waiting\n  at com.android.se.fixture.WaitForHal.wait(WaitForHal.java:42)\n'
SE_TRACE = (
    '----- pid 10 -----\nCmd line: unrelated.before\nSECRET_BEFORE_PROCESS\n'
    '----- end 10 -----\n'
    '----- pid 20 -----\nCmd line: com.android.se\n'
    + SE_STACK
    + '----- end 20 -----\n'
    '----- pid 30 -----\nCmd line: unrelated.after\nSECRET_AFTER_PROCESS\n'
    '----- end 30 -----\n'
)
TIKTOK_PACKAGE = 'com.zhiliaoapp.musically'


def tiktok_trace(marker, *, secondary=False, package=TIKTOK_PACKAGE, lines=1):
    prefix = (
        '----- pid 10 -----\nCmd line: unrelated.before\nSECRET_TIKTOK_PREFIX\n'
        '----- end 10 -----\n'
        if secondary else ''
    )
    return (
        prefix + '----- pid 40 -----\nCmd line: ' + package + '\n'
        + ''.join(f'{marker}_{number:03d}\n' for number in range(lines))
        + '----- end 40 -----\n'
        '----- pid 50 -----\nCmd line: unrelated.after\nSECRET_TIKTOK_SUFFIX\n'
        '----- end 50 -----\n'
    )


class SecureElementDiagnosticTests(unittest.TestCase):
    def run_report(self, *, primary_process='com.android.se', traces=None,
                   lshal_timeout=False, trace_budget_expired=False):
        if traces is None:
            traces = [('anr_fixture', SE_TRACE)]
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)

            def put(name, contents):
                path = sandbox / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
                return path

            for name in ['Download', 'tmp', 'anr', 'proc', 'sys', 'bin']:
                (sandbox / name).mkdir()
            put('proc/version', 'fixture kernel; must remain unchanged\n')
            put('proc/sys/vm/swappiness', '100\n')
            put('proc/sys/kernel/random/boot_id', 'fixture-boot-id\n')
            put('sys/kernel/mm/lru_gen/enabled', '0x0001\n')
            put('sys/class/power_supply/battery/temp', '480\n')
            put('sys/class/power_supply/battery/status', 'Charging\n')
            for field, value in [('scaling_min_freq', '300000'),
                                 ('scaling_max_freq', '806400'),
                                 ('cpuinfo_max_freq', '2400000')]:
                put('sys/devices/system/cpu/cpufreq/policy0/' + field, value + '\n')
            for number in range(34):
                device = f'sys/class/thermal/cooling_device{number:02d}/'
                put(device + 'type', f'cpu-cooling-{number}\n' if number < 32 else 'SECRET_EXTRA_COOLING\n')
                put(device + 'cur_state', '5\n')
                put(device + 'max_state', '10\n')
            for index, (name, contents) in enumerate(traces):
                trace = put('anr/' + name, contents)
                # List order is deterministic even on coarse timestamp filesystems.
                timestamp = 1700000000 - index * 10
                os.utime(trace, (timestamp, timestamp))

            def system_snapshot():
                return {
                    str(path.relative_to(sandbox)): (path.read_bytes(), path.stat().st_mode)
                    for folder in ['proc', 'sys', 'anr']
                    for path in (sandbox / folder).rglob('*')
                    if path.is_file()
                }

            before = system_snapshot()
            allowed_process = primary_process in (
                'com.android.se', TIKTOK_PACKAGE, 'com.ss.android.ugc.trill',
            )
            reason = ('executing service com.android.se/.SecureElementService'
                      if primary_process == 'com.android.se' else 'Input dispatching timed out')
            anr = put(
                'fixture-lastanr',
                'ANR time: 2026-10-23 17:04:32\n'
                f'ANR in {primary_process}\nProcess: {primary_process}\nPID: 20\n'
                f'Reason: {reason}\n'
                'SECRET_UNSELECTED_SUMMARY_STATE\n'
                if allowed_process else
                'ANR time: 2026-10-23 17:04:32\n'
                'ANR in unrelated.app\nProcess: unrelated.app\n'
                'Reason: SECRET_OTHER_APP_REASON\n'
                'CPU usage: com.android.se and com.zhiliaoapp.musically are secondary\n'
                'Process: com.android.se\n',
            )
            calls = put('fixture-calls', '')
            epoch_calls = put('fixture-epoch-calls', '0\n')
            thermal = put('fixture-thermal', 'Thermal Status: 3\n'
                          + 'Temperature fixture\n' * 99 + 'SECRET_THERMAL_TAIL\n')
            commands = {
                'id': '[ "$*" = "-u" ] || exit 91; printf "0\\n"',
                'uname': '[ "$*" = "-r" ] || exit 91; printf "5.15.216-fixture\\n"',
                'getprop': 'printf "fixture-%s\\n" "$1"',
                'dumpsys': '''case "$*" in
"activity lastanr") cat "$FIXTURE_LASTANR";;
"thermalservice") cat "$FIXTURE_THERMAL";;
*) exit 91;;
esac''',
                'pm': '''[ "$*" = "list features" ] || exit 91
printf '%s\\n' 'feature:android.hardware.se.omapi.ese' 'feature:SECRET_FEATURE_NOISE' ''',
                'service': '''[ "$*" = "list" ] || exit 91
printf '%s\\n' '12 secure_element: [android.se.omapi.ISecureElementService]' '13 SECRET_SERVICE_NOISE: [private.Interface]' ''',
                'lshal': '''[ "$#" = 0 ] || exit 91
printf '%s\\n' 'android.hardware.secure_element@1.2::ISecureElement/eSE1' 'SECRET_HAL_NOISE'
[ "$FIXTURE_LSHAL_TIMEOUT" = 1 ] && exit 124
exit 0''',
                'logcat': '''case " $* " in *' -c '*) exit 91;; esac
printf '%s\\n' \
 '10-23 17:04:32.462 I am_kill: [0,20,com.android.se,-800,bg anr]' \
 '10-23 17:04:32.463 I am_anr: [0,20,com.android.se,1,SE_FIXTURE_ANR_EVENT]' \
 '10-23 17:04:32.464 I am_anr: [0,30,unrelated.app,1,SECRET_OTHER_EVENT]' ''',
                'date': '''if [ "$*" = '+%s' ] && [ "$FIXTURE_TRACE_BUDGET_EXPIRED" = 1 ]; then
  epoch_calls=$(cat "$FIXTURE_EPOCH_CALLS")
  printf '%s\\n' "$((1700000000 + epoch_calls * 21))"
  printf '%s\\n' "$((epoch_calls + 1))" > "$FIXTURE_EPOCH_CALLS"
else
  /bin/date "$@"
fi''',
                'timeout': '''case "$1" in 1|2|3|4|5|6) ;; *) exit 91;; esac
shift
"$@"''',
            }
            for name, body in commands.items():
                command = put(
                    'bin/' + name,
                    '#!/bin/sh\n'
                    'printf "%s %s\\n" "${0##*/}" "$*" >> "$FIXTURE_CALLS"\n'
                    + body + '\n',
                )
                command.chmod(0o755)

            source = (ROOT / 'scripts/chatgpt-secureelement-logs.sh').read_text()
            original_path = 'PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin'
            self.assertIn(original_path, source)
            source = source.replace(original_path, f'PATH={sandbox / "bin"}:/usr/bin:/bin')
            for original, replacement in [
                ('/sdcard/Download', str(sandbox / 'Download')),
                ('/data/local/tmp', str(sandbox / 'tmp')),
                ('/data/anr', str(sandbox / 'anr')),
                ('/proc/', str(sandbox / 'proc') + '/'),
                ('/sys/', str(sandbox / 'sys') + '/'),
            ]:
                source = source.replace(original, replacement)
            script = put('secureelement-collector.sh', source)
            environment = dict(
                os.environ,
                FIXTURE_LASTANR=str(anr),
                FIXTURE_CALLS=str(calls),
                FIXTURE_LSHAL_TIMEOUT='1' if lshal_timeout else '0',
                FIXTURE_THERMAL=str(thermal),
                FIXTURE_EPOCH_CALLS=str(epoch_calls),
                FIXTURE_TRACE_BUDGET_EXPIRED='1' if trace_budget_expired else '0',
            )
            result = subprocess.run(
                ['/bin/sh', str(script)], env=environment,
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Done. Share this one text file:', result.stdout)
            reports = list((sandbox / 'Download').glob('ChatGPTKernel-SE-*.txt'))
            self.assertEqual(len(reports), 1)
            self.assertIn(str(reports[0]), result.stdout)
            contents = reports[0].read_text()
            self.assertIn('=== FINISHED ===', contents)
            self.assertIn('No settings or services were changed', contents)
            self.assertIn('android.se.omapi.ISecureElementService', contents)
            self.assertIn('feature:android.hardware.se.omapi.ese', contents)
            self.assertIn('SE_FIXTURE_ANR_EVENT', contents)
            self.assertIn('battery temperature (tenths C): 480', contents)
            self.assertIn('battery status: Charging', contents)
            self.assertIn('scaling_max_freq: 806400', contents)
            self.assertIn('cpuinfo_max_freq: 2400000', contents)
            self.assertIn('cpu-cooling-31', contents)
            self.assertIn('Thermal Status: 3', contents)
            self.assertIn('thermalservice exit status: 0', contents)
            self.assertNotIn('SECRET_', contents)
            self.assertEqual(system_snapshot(), before)
            self.assertEqual(list((sandbox / 'tmp').iterdir()), [])
            invocations = calls.read_text()
            self.assertIn('dumpsys activity lastanr\n', invocations)
            self.assertIn('pm list features\n', invocations)
            self.assertIn('service list\n', invocations)
            self.assertIn('timeout 6 lshal\n', invocations)
            self.assertIn('timeout 6 dumpsys thermalservice\n', invocations)
            self.assertNotIn('exit status: 91', contents)
            return contents

    def test_primary_secureelement_anr_and_only_its_stack(self):
        report = self.run_report()
        self.assertIn('Reason: executing service com.android.se/.SecureElementService', report)
        self.assertIn(SE_STACK, report)
        self.assertIn('presence alone does not identify the ANR victim', report)
        self.assertNotIn('Cmd line: unrelated.', report)

    def test_other_primary_anr_with_secondary_secureelement_is_not_misattributed(self):
        report = self.run_report(primary_process='unrelated.app')
        self.assertIn('No primary SecureElement/TikTok ANR summary; other-app contents omitted.', report)
        self.assertIn(SE_STACK, report)
        self.assertNotIn('ANR in unrelated.app', report)
        self.assertNotIn('Reason: executing service', report)

    def test_no_traces_and_hal_timeout_are_explicit(self):
        report = self.run_report(traces=[], lshal_timeout=True)
        self.assertIn('No readable SecureElement process section found', report)
        self.assertIn('lshal exit status: 124', report)

    def test_secureelement_in_fourth_oldest_trace_is_not_reported(self):
        other = '----- pid 30 -----\nCmd line: unrelated.app\nSECRET_OLD_TRACE\n----- end 30 -----\n'
        traces = [('anr_' + str(i), other) for i in range(3)]
        traces.append(('anr_older_secureelement', SE_TRACE))
        report = self.run_report(traces=traces)
        self.assertIn('No readable SecureElement process section found', report)
        self.assertNotIn(SE_STACK, report)

    def test_primary_tiktok_trace_beats_newer_secondary_and_summary_is_allowed(self):
        report = self.run_report(primary_process=TIKTOK_PACKAGE, traces=[
            ('anr_new_secondary', tiktok_trace('SECONDARY_STACK', secondary=True)),
            ('anr_older_primary', tiktok_trace('PRIMARY_STACK')),
        ])
        self.assertIn('ANR in ' + TIKTOK_PACKAGE, report)
        self.assertIn('Reason: Input dispatching timed out', report)
        self.assertIn('Trace role: primary (first Cmd line is TikTok).', report)
        self.assertIn('anr_older_primary', report)
        self.assertIn('mtime epoch: 1699999990', report)
        self.assertIn('PRIMARY_STACK_000', report)
        self.assertNotIn('SECONDARY_STACK', report)

    def test_tiktok_secondary_fallback_and_trill_package(self):
        report = self.run_report(traces=[
            ('anr_secondary', tiktok_trace('SECONDARY_STACK', secondary=True,
                                         package='com.ss.android.ugc.trill')),
        ])
        self.assertIn('Trace role: secondary;', report)
        self.assertIn('SECONDARY_STACK_000', report)
        self.assertIn('mtime epoch: 1700000000', report)

    def test_tiktok_trace_search_stops_at_32_files(self):
        other = '----- pid 10 -----\nCmd line: unrelated.app\nSECRET_TRACE\n----- end 10 -----\n'
        traces = [('anr_' + str(i), other) for i in range(32)]
        traces.append(('anr_excluded_33', tiktok_trace('EXCLUDED_STACK')))
        report = self.run_report(traces=traces)
        self.assertIn('No readable TikTok process section found in the 32 newest traces.', report)
        self.assertNotIn('EXCLUDED_STACK', report)

    def test_tiktok_block_is_limited_to_260_lines(self):
        report = self.run_report(traces=[('anr_large', tiktok_trace('LIMIT_STACK', lines=400))])
        block = report.split('Cmd line: ' + TIKTOK_PACKAGE + '\n', 1)[1].split('\n===', 1)[0]
        self.assertEqual(len([line for line in block.splitlines() if line]), 259)
        self.assertIn('LIMIT_STACK_258', report)
        self.assertNotIn('LIMIT_STACK_259', report)

    def test_tiktok_trace_search_budget_exhaustion_is_explicit(self):
        report = self.run_report(trace_budget_expired=True)
        self.assertIn('20-second time budget exhausted', report)

    def test_missing_end_markers_do_not_disclose_the_next_process(self):
        suffix = '----- pid 90 -----\nCmd line: unrelated.app\nSECRET_INTERRUPTED_TRACE\n----- end 90 -----\n'
        report = self.run_report(traces=[
            ('anr_interrupted_se', '----- pid 20 -----\nCmd line: com.android.se\n' + SE_STACK + suffix),
            ('anr_interrupted_tiktok', '----- pid 40 -----\nCmd line: ' + TIKTOK_PACKAGE
             + '\nTIKTOK_INTERRUPTED_STACK\n' + suffix),
        ])
        self.assertIn(SE_STACK, report)
        self.assertIn('TIKTOK_INTERRUPTED_STACK', report)
        self.assertNotIn('Cmd line: unrelated.app', report)


if __name__ == '__main__':
    unittest.main()
