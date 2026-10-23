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


class SecureElementDiagnosticTests(unittest.TestCase):
    def run_report(self, *, primary_se=True, traces=None, lshal_timeout=False):
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
            anr = put(
                'fixture-lastanr',
                'ANR time: 2026-10-23 17:04:32\n'
                'ANR in com.android.se\nProcess: com.android.se\nPID: 20\n'
                'Reason: executing service com.android.se/.SecureElementService\n'
                'SECRET_UNSELECTED_SUMMARY_STATE\n'
                if primary_se else
                'ANR time: 2026-10-23 17:04:32\n'
                'ANR in unrelated.app\nProcess: unrelated.app\n'
                'Reason: SECRET_OTHER_APP_REASON\n'
                'CPU usage: com.android.se is a secondary process\n',
            )
            calls = put('fixture-calls', '')
            commands = {
                'id': '[ "$*" = "-u" ] || exit 91; printf "0\\n"',
                'uname': '[ "$*" = "-r" ] || exit 91; printf "5.15.216-fixture\\n"',
                'getprop': 'printf "fixture-%s\\n" "$1"',
                'dumpsys': '''[ "$*" = "activity lastanr" ] || exit 91
cat "$FIXTURE_LASTANR"''',
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
                'timeout': '''[ "$1" = 6 ] || exit 91
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
            self.assertNotIn('SECRET_', contents)
            self.assertEqual(system_snapshot(), before)
            self.assertEqual(list((sandbox / 'tmp').iterdir()), [])
            invocations = calls.read_text()
            self.assertIn('dumpsys activity lastanr\n', invocations)
            self.assertIn('pm list features\n', invocations)
            self.assertIn('service list\n', invocations)
            self.assertIn('timeout 6 lshal\n', invocations)
            self.assertNotIn('exit status: 91', contents)
            return contents

    def test_primary_secureelement_anr_and_only_its_stack(self):
        report = self.run_report()
        self.assertIn('Reason: executing service com.android.se/.SecureElementService', report)
        self.assertIn(SE_STACK, report)
        self.assertIn('presence alone does not identify the ANR victim', report)
        self.assertNotIn('Cmd line: unrelated.', report)

    def test_other_primary_anr_with_secondary_secureelement_is_not_misattributed(self):
        report = self.run_report(primary_se=False)
        self.assertIn('No primary SecureElement ANR summary; other-app contents omitted.', report)
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


if __name__ == '__main__':
    unittest.main()
