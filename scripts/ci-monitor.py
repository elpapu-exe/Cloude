#!/usr/bin/env python3
"""Sample CI capacity and PSI during compilation without collecting environment values."""
import json
from pathlib import Path
import runpy
import time

resource_report = runpy.run_path(str(Path(__file__).with_name('ci-resource-report.py')))['resource_report']
while True:
    report = resource_report()
    report['pressure'] = {}
    for name in ('memory', 'cpu', 'io'):
        path = Path('/proc/pressure') / name
        if path.is_file():
            report['pressure'][name] = path.read_text().strip()
    print(json.dumps(report, separators=(',', ':')), flush=True)
    time.sleep(15)
