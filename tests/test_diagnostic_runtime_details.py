#!/usr/bin/env python3
"""Small format/absence fixtures for the collector's read-only runtime details."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeDetailTests(unittest.TestCase):
    def capture(self, populated):
        with tempfile.TemporaryDirectory(prefix='runtime-detail-') as directory:
            sandbox = Path(directory)
            fixtures = {
                'sys/block/sda/queue/scheduler': 'none mq-deadline [ssg]\n',
                'sys/block/sda/mq/0/fixture': '',
                'sys/block/sda/mq/1/fixture': '',
                'sys/block/mmcblk0/queue/scheduler': '[mq-deadline] none\n',
                'sys/block/mmcblk0/mq/0/fixture': '',
                'proc/diskstats': '8 0 sda 12 0 800 4 20 0 1600 8 1 13 17 0 0 0 0\n253 0 dm-0 30 0 2000 8 40 0 3000 15 0 23 25\n7 0 loop0 1 2 3 4 5 6 7 8 9 10 11\n',
                'proc/modules': 'qcom_cpufreq_hw 20480 1 - Live 0xffff0000\nmsm_kgsl 901120 2 dep, Live 0xffff1111\nbad$module 55 1 - Live 0xffff2222\n',
                'sys/devices/system/cpu/cpufreq/policy0/scaling_governor': 'schedutil\n',
                'sys/devices/system/cpu/cpufreq/policy0/scaling_driver': 'qcom-cpufreq-hw\n',
                'sys/devices/system/cpu/cpufreq/policy0/schedutil/rate_limit_us': '2000\n',
                'sys/devices/system/cpu/cpufreq/schedutil/rate_limit_us': '1500\n',
                'sys/devices/system/cpu/cpufreq/policy4/scaling_governor': 'schedhorizon\n',
                'sys/devices/system/cpu/cpufreq/policy4/schedhorizon/up_rate_limit_us': '500\n',
                'sys/devices/system/cpu/cpufreq/policy4/schedhorizon/down_rate_limit_us': '1000\n',
                'sys/devices/system/cpu/cpufreq/schedhorizon/up_rate_limit_us': '900\n',
                'sys/class/kgsl/kgsl-3d0/gpu_model': 'Adreno fixture\n',
                'sys/class/kgsl/kgsl-3d0/gpuclk': '680000000\n',
                'sys/class/kgsl/kgsl-3d0/devfreq/governor': 'msm-adreno-tz\n',
                'sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies': '680000000 465000000\n',
                'dev/cpuset/top-app/cpus': '0-7\n',
                'dev/cpuset/foreground/cpus': '0-5\n',
                'dev/cpuctl/top-app/cpu.uclamp.min': '10.00\n',
                'dev/cpuctl/top-app/cpu.uclamp.max': 'max\n',
                'dev/cpuset/top-app/tasks': 'PRIVATE_TASK_MEMBERSHIP\n',
                'proc/meminfo': 'MemTotal: 123 kB\nCmaTotal: 16384 kB\nCmaFree: 2048 kB\n',
                'proc/vmstat': 'kswapd_low_wmark_hit_quickly 12\nkswapd_high_wmark_hit_quickly 34\n',
                'proc/stat': 'cpu 1 2 3 4\n',
                'data/adb/chatgpt-cpu-respuesta/history.log': 'APPLIED policy0: 40000 -> 30000\n',
                'data/adb/chatgpt-cpu-respuesta/paused': '',
                'data/adb/unrelated-private-module/history.log': 'PRIVATE_OTHER_MODULE_DATA\n',
                'sys/class/power_supply/battery/temp': '350\n',
            } if populated else {}
            for name, value in fixtures.items():
                target = sandbox / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value)
            # No background worker or log capture is run: only defined readers.
            source = (ROOT / 'scripts/chatgpt-kernel-logs.sh').read_text()
            source = source[:source.index('[ "$(id -u)" = 0 ]')]
            source = source.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin', 'PATH=/usr/bin:/bin')
            for prefix in ('/sys/', '/proc/', '/dev/cpuset/', '/dev/cpuctl/', '/data/adb/'):
                source = source.replace(prefix, str(sandbox / prefix.strip('/')) + '/')
            thermal = sandbox / 'thermal-paths'
            thermal.write_text('')
            # settings is unrelated to these fixtures and has no host equivalent.
            source += '\nsettings() { printf "NA\\n"; }\n'
            source += f'LOCK="{sandbox}"\nown_module_profiles BEGIN\nconfiguration\nruntime_hardware\nio_configuration BEGIN\nio_configuration END\nsnapshot fixture\n'
            script = sandbox / 'details.sh'
            script.write_text(source)
            result = subprocess.run(['/bin/sh', str(script)], text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name, value in fixtures.items():
                self.assertEqual((sandbox / name).read_text(), value)
            return result.stdout

    def test_runtime_fields_have_bounded_safe_format(self):
        output = self.capture(True)
        for expected in ('scaling_driver: qcom-cpufreq-hw', 'rate_limit_us: 2000',
                         'rate_limit_us: 1500', 'up_rate_limit_us: 500',
                         'down_rate_limit_us: 1000', 'up_rate_limit_us: 900',
                         'qcom_cpufreq_hw 20480 1', 'msm_kgsl 901120 2',
                         'KGSL gpu_model: Adreno fixture', 'KGSL gpuclk: 680000000',
                         'governor: msm-adreno-tz', 'available_frequencies: 680000000 465000000',
                         'top-app/cpus: 0-7', 'foreground/cpus: 0-5',
                         'cpu.uclamp.min: 10.00', 'cpu.uclamp.max: max',
                         'CmaTotal: 16384 kB', 'CmaFree: 2048 kB',
                         'kswapd_low_wmark_hit_quickly 12', 'kswapd_high_wmark_hit_quickly 34',
                         'sda scheduler: none mq-deadline [ssg]', 'sda hardware queue count: 2',
                         'mmcblk0 hardware queue count: 1', 'sda 12 800 4 20 1600 8 1 13 17',
                         'dm-0 30 2000 8 40 3000 15 0 23 25', 'Block I/O BEGIN', 'Block I/O END', 'APPLIED policy0: 40000 -> 30000', 'pause_marker: present'):
            self.assertIn(expected, output)
        for forbidden in ('0xffff', 'PRIVATE_TASK_MEMBERSHIP', 'bad$module', 'loop0', 'PRIVATE_OTHER_MODULE_DATA'):
            self.assertNotIn(forbidden, output)

    def test_absent_optional_interfaces_report_na(self):
        output = self.capture(False)
        self.assertIn('KGSL gpu_model: NA', output)
        self.assertIn('cpu.uclamp.min: NA', output)
        self.assertIn('name bytes refs\nNA', output)
        self.assertNotIn('0xffff', output)


    def test_profile_history_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory(prefix='profile-history-') as directory:
            sandbox = Path(directory)
            private = sandbox / 'private'
            private.write_text('PRIVATE_HISTORY_TARGET\n')
            profile = sandbox / 'data/adb/chatgpt-cpu-respuesta'
            profile.mkdir(parents=True)
            (profile / 'history.log').symlink_to(private)
            source = (ROOT / 'scripts/chatgpt-kernel-logs.sh').read_text()
            source = source[:source.index('[ "$(id -u)" = 0 ]')]
            source = source.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin', 'PATH=/usr/bin:/bin')
            source = source.replace('/data/adb/', str(sandbox / 'data/adb') + '/')
            script = sandbox / 'profile.sh'
            script.write_text(source + '\nown_module_profiles BEGIN\n')
            result = subprocess.run(['/bin/sh', str(script)], text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('PRIVATE_HISTORY_TARGET', result.stdout)
            self.assertIn('Own profile history: NA', result.stdout)
            self.assertEqual(private.read_text(), 'PRIVATE_HISTORY_TARGET\n')


if __name__ == '__main__':
    unittest.main()
