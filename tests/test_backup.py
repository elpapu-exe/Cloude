#!/usr/bin/env python3
"""Exercise backup failure paths without any block device or phone access."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class BackupTests(unittest.TestCase):
    def run_backup(self, *, expected=8192, fail_copy=False, corrupt_hash=False):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            original = bytes(range(256)) * 32
            (target / 'original.img').write_bytes(original)
            (target / 'Download').mkdir()
            # Redirect phone storage paths only; all backup operations are real.
            source = (ROOT / 'installer/chatgpt-backup.sh').read_text()
            source = source.replace('/sdcard/Download /data/media/0/Download', '"$TEST_ROOT/Download"')
            (target / 'backup.sh').write_text(source)
            setup = '''
set -eu
abort() { printf '%s\n' "$*" >&2; exit 1; }
ui_print() { :; }
blockdev() { printf '%s\n' "$EXPECTED"; }
BOOTIMG="$TEST_ROOT/original.img"
BLOCK=/dev/block/by-name/boot_a
SLOT=_a
. "$TEST_ROOT/backup.sh"
'''
            if fail_copy:
                setup += 'cp() { return 1; }\n'
            if corrupt_hash:
                setup += '''sha256sum() {
case "$1" in */boot.img) printf 'bad  boot.img\n';; *) command sha256sum "$@";; esac
}\n'''
            setup += 'chatgpt_backup_boot\nprintf OK > "$TEST_ROOT/can-flash"\n'
            import os
            env = dict(os.environ, TEST_ROOT=str(target), EXPECTED=str(expected))
            result = subprocess.run(['bash', '-c', setup], env=env, capture_output=True, text=True)
            if expected != 8192 or fail_copy or corrupt_hash:
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((target / 'can-flash').exists())
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                backups = list((target / 'Download').glob('ChatGPTKernel-backups/*/boot.img'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), original)
                digest = hashlib.sha256(original).hexdigest()
                self.assertIn(digest, (backups[0].parent / 'SHA256SUMS').read_text())
                self.assertTrue((target / 'can-flash').exists())

    def test_verified_copy(self): self.run_backup()
    def test_incomplete_dump_aborts(self): self.run_backup(expected=9000)
    def test_copy_failure_aborts(self): self.run_backup(fail_copy=True)
    def test_hash_mismatch_aborts(self): self.run_backup(corrupt_hash=True)

if __name__ == '__main__': unittest.main()
