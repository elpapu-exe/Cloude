#!/usr/bin/env python3
"""Run the Android collector with fake system files, without root or a phone."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DiagnosticTests(unittest.TestCase):
    def run_worker(self, *, tiktok_anr):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            def put(name, contents):
                path = sandbox / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
                return path
            fixtures = {
                'proc/uptime': '600.00 2000.00\n',
                'proc/version': 'Test fixture kernel\n',
                'proc/meminfo': 'MemTotal: 3744164 kB\nMemAvailable: 700000 kB\nSwapTotal: 3145724 kB\nSwapFree: 8996 kB\n',
                'proc/stat': 'cpu 10 0 20 300 0 0 0 0\n',
                'proc/loadavg': '1.00 0.80 0.50 1/100 99\n',
                'proc/vmstat': 'pswpin 5\npswpout 20\npgscan_direct 100\nworkingset_refault_file 10\noom_kill 0\n',
                'proc/swaps': 'Filename Type Size Used Priority\n/dev/block/zram0 partition 3145724 3136728 -2\n',
                'proc/pressure/memory': 'some avg10=74.43 total=1000\nfull avg10=36.75 total=500\n',
                'proc/pressure/cpu': 'some avg10=1.00 total=50\n',
                'proc/pressure/io': 'some avg10=0.00 total=0\n',
                'sys/kernel/mm/lru_gen/enabled': '0x0007\n',
                'sys/kernel/mm/lru_gen/min_ttl_ms': '0\n',
                'sys/block/zram0/mm_stat': '3211984896 1064400246 1113079808 0 1290207232 76855 17689648 41382 6450814\n',
                'sys/class/power_supply/battery/temp': '370\n',
                'sys/class/power_supply/battery/status': 'Discharging\n',
                'sys/class/thermal/thermal_zone0/type': 'cpu-0-0-usr\n',
                'sys/class/thermal/thermal_zone0/temp': '52000\n',
                'sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq': '1800000\n',
                'sys/devices/system/cpu/cpufreq/policy0/scaling_governor': 'schedhorizon\n',
            }
            for name, value in fixtures.items(): put(name, value)
            lock = sandbox / 'tmp/chatgpt-kernel-logger.lock'
            lock.mkdir(parents=True)
            put('tmp/chatgpt-kernel-logger.lock/pid', '123\n')
            put('tmp/chatgpt-kernel-logger.lock/bootid', 'fixture\n')
            bins = sandbox / 'bin'; bins.mkdir()
            commands = {
                'id': 'printf "0\\n"',
                'sleep': ':',
                'getprop': 'printf "fixture\\n"',
                'ps': 'printf "PID CPU RSS NAME\\n100 20 500000 com.zhiliaoapp.musically\\n"',
                'top': 'printf "CPU fixture\\n100 com.zhiliaoapp.musically\\n"',
                'logcat': 'printf "selected diagnostic event\\n"',
                'dmesg': 'printf "[1.0] CFI failure fixture\\n[2.0] unrelated line\\n"',
                'dumpsys': '''case "$1 $2" in
"activity lastanr") cat "$FIXTURE_ANR";;
"package "*) printf 'versionName=1.0\\nversionCode=10\\n';;
"meminfo "*) printf 'TOTAL PSS: 646469 TOTAL SWAP PSS: 279234\\nObjects\\nDATABASES\\nACCOUNT_IDENTIFIER_NOT_FOR_REPORT\\n';;
esac''',
            }
            for name, body in commands.items():
                command = put('bin/' + name, '#!/bin/sh\n' + body + '\n')
                command.chmod(0o755)
            anr = put('fixture-anr', 'ANR in com.zhiliaoapp.musically\nReason: Input dispatch timeout\n' if tiktok_anr else 'ANR in unrelated.app\nReason: SECRET_URI\nCPU: com.zhiliaoapp.musically\n')
            trace = put('anr/anr_fixture', '----- pid 100 -----\nCmd line: com.zhiliaoapp.musically\n"main" waiting in fixture\n----- end 100 -----\nCmd line: unrelated.app\nSECRET_OTHER_PROCESS\n')
            import time
            os.utime(trace, (time.time() + 5, time.time() + 5))
            source = (ROOT / 'scripts/chatgpt-kernel-logs.sh').read_text()
            source = source.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin', f'PATH={bins}:/usr/bin:/bin')
            for original, replacement in [('/sdcard/Download', str(sandbox / 'Download')), ('/data/local/tmp', str(sandbox / 'tmp')), ('/data/anr', str(sandbox / 'anr')), ('/proc/', str(sandbox / 'proc') + '/'), ('/sys/', str(sandbox / 'sys') + '/')]:
                source = source.replace(original, replacement)
            script = put('collector.sh', source)
            output = sandbox / 'result.txt'
            environment = dict(os.environ, FIXTURE_ANR=str(anr))
            result = subprocess.run(['/bin/sh', str(script), '--worker', str(output), '60'], env=environment, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            contents = output.read_text()
            self.assertEqual(contents.count('=== Sample '), 7)
            self.assertIn('TEST FINISHED:', contents)
            self.assertIn('some avg10=74.43', contents)
            self.assertIn('0x0007', contents)
            self.assertIn('TOTAL SWAP PSS: 279234', contents)
            self.assertIn('"main" waiting in fixture', contents)
            self.assertNotIn('SECRET_URI', contents)
            self.assertNotIn('SECRET_OTHER_PROCESS', contents)
            self.assertNotIn('ACCOUNT_IDENTIFIER_NOT_FOR_REPORT', contents)
            if tiktok_anr:
                self.assertIn('Reason: Input dispatch timeout', contents)
            else:
                self.assertIn('other-app contents omitted', contents)
            self.assertFalse(lock.exists())
            for name, value in fixtures.items(): self.assertEqual((sandbox / name).read_text(), value)

    def test_tiktok_anr_and_unchanged_system_files(self): self.run_worker(tiktok_anr=True)
    def test_other_app_anr_omitted(self): self.run_worker(tiktok_anr=False)

if __name__ == '__main__': unittest.main()
