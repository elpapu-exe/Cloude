#!/usr/bin/env python3
"""Required release regressions: absent files, failures and skips block packaging."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from source_path import SOURCE_ROOT
FILES = ('test_ci_resources.py', 'test_backup.py', 'test_manual_boot_backup.py', 'test_source_acquisition.py',
         'test_schedhorizon_tunables.py', 'test_schedhorizon_frequency.py',
         'test_mglru_accounting.py', 'test_ssg_safety.py',
         'test_ssg_request_capacity.py', 'test_mglru_reclaim.py',
         'test_binder_async_quota.py', 'test_cpufreq_start_serialization.py',
         'test_f2fs_range_safety.py', 'test_mglru_cache_protection.py',
         'test_mglru_cma.py', 'test_diagnostic.py',
         'test_diagnostic_runtime_details.py')
suite = unittest.TestSuite()
counts = {}
for name in FILES:
    assert (ROOT / 'tests' / name).is_file(), f'Required test missing: {name}'
    loaded = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=name)
    counts[name] = loaded.countTestCases()
    assert counts[name] > 0, f'Empty required suite: {name}'
    suite.addTests(loaded)
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {'source_root': str(SOURCE_ROOT), 'tests_run': result.testsRun, 'files': counts, 'failures': len(result.failures),
          'errors': len(result.errors), 'skips': len(result.skipped),
          'scope': 'host unit and regression checks; no device validation'}
(ROOT / 'logs').mkdir(exist_ok=True)
(ROOT / 'logs/release-tests.json').write_text(json.dumps(report, indent=2) + '\n')
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
