#!/usr/bin/env python3
"""Verify the manual backup using ordinary files; never access a block device."""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ManualBootBackupTests(unittest.TestCase):
    def run_backup(self, *, slot='_a', slot_name='a', size=8192,
                   fail_copy=False, bad_hash=False, collision=False):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            bins = sandbox / 'bin'
            bins.mkdir()
            downloads = sandbox / 'Download'
            downloads.mkdir()
            block = sandbox / 'block/by-name'
            block.mkdir(parents=True)
            original = bytes(range(256)) * 32
            (block / 'boot_a').write_bytes(original)
            (block / 'boot_b').write_bytes(original)
            commands = {
                'id': 'printf "0\\n"',
                'getprop': '''case "$1" in
ro.product.device) printf 'tapas\\n';;
ro.boot.slot_suffix) printf '%s\\n' "$FIXTURE_SLOT";;
ro.boot.slot) printf '%s\\n' "$FIXTURE_SLOT_NAME";;
ro.build.display.id) printf 'lineage_topaz fixture\\n';;
esac''',
                'blockdev': 'printf "%s\\n" "$FIXTURE_SIZE"',
                'date': 'printf "20261028T040000Z\\n"',
                'sync': ':',
            }
            if fail_copy:
                commands['dd'] = 'exit 1'
            if bad_hash:
                commands['sha256sum'] = '''case "$1" in
*/block/by-name/boot_a) printf '%064d  %s\\n' 0 "$1";;
*) /usr/bin/sha256sum "$@";;
esac'''
            for name, body in commands.items():
                command = bins / name
                command.write_text('#!/bin/sh\n' + body + '\n')
                command.chmod(0o755)
            source = (ROOT / 'scripts/chatgpt-backup-current.sh').read_text()
            source = source.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin',
                                    f'PATH={bins}:/usr/bin:/bin')
            source = source.replace('/dev/block/', str(sandbox / 'block') + '/')
            source = source.replace('/sdcard/Download', str(downloads))
            source = source.replace('[ -b "$candidate" ]', '[ -f "$candidate" ]')
            source = source.replace('${SLOT_SUFFIX}-$$', '${SLOT_SUFFIX}-fixed')
            script = sandbox / 'backup.sh'
            script.write_text(source)
            effective_slot = slot if slot in ('_a', '_b') else '_' + slot_name if slot == '' and slot_name in ('a', 'b') else '_a'
            target = downloads / f'ChatGPTKernel-backups/manual-20261028T040000Z{effective_slot}-fixed'
            if collision:
                target.mkdir(parents=True)
                (target / 'boot.img').write_bytes(b'PREVIOUS_BACKUP')
            env = dict(os.environ, FIXTURE_SLOT=slot, FIXTURE_SLOT_NAME=slot_name,
                       FIXTURE_SIZE=str(size))
            result = subprocess.run(['/bin/sh', str(script)], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual((block / 'boot_a').read_bytes(), original)
            self.assertEqual((block / 'boot_b').read_bytes(), original)
            slot_valid = slot in ('_a', '_b') or slot == '' and slot_name in ('a', 'b')
            properties_agree = slot_name == '' or slot_name in ('a', 'b') and '_' + slot_name == effective_slot
            fails = fail_copy or bad_hash or size != len(original) or not slot_valid or not properties_agree or collision
            if fails:
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('VERIFIED:', result.stdout)
                if collision:
                    self.assertEqual((target / 'boot.img').read_bytes(), b'PREVIOUS_BACKUP')
                else:
                    self.assertFalse((target / 'boot.img').exists())
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('VERIFIED:', result.stdout)
                self.assertEqual((target / 'boot.img').read_bytes(), original)
                self.assertEqual((target / 'SHA256SUMS').read_text(),
                                 hashlib.sha256(original).hexdigest() + '  boot.img\n')
                self.assertIn('Slot: ' + effective_slot, (target / 'backup-info.txt').read_text())
                self.assertFalse((target / 'boot.img.partial').exists())

    def test_full_copy_size_and_hash_match(self):
        self.run_backup()
        self.run_backup(slot='_b', slot_name='b')
        self.run_backup(slot='', slot_name='a')
        self.run_backup(slot='_a', slot_name='')

    def test_invalid_slot_and_disagreeing_properties_abort(self):
        self.run_backup(slot='../../other')
        self.run_backup(slot='_a', slot_name='b')

    def test_dd_failure_does_not_publish_final_backup(self):
        self.run_backup(fail_copy=True)

    def test_incomplete_dump_does_not_publish_final_backup(self):
        self.run_backup(size=9000)

    def test_hash_mismatch_does_not_publish_final_backup(self):
        self.run_backup(bad_hash=True)

    def test_existing_backup_is_never_overwritten(self):
        self.run_backup(collision=True)


if __name__ == '__main__':
    unittest.main()
