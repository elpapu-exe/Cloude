#!/system/bin/sh
# Read the active boot partition. Write only a new backup directory in Download.
# Never flashes, changes slots, writes block devices, or uploads the backup.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077
set -C

fail() {
  printf 'Backup failed: %s\nNo partition was written.\n' "$*" >&2
  [ -z "${BACKUP_DIR:-}" ] || printf 'Incomplete backup directory: %s\nDo not use it for recovery.\n' "$BACKUP_DIR" >&2
  exit 1
}

[ "$#" -eq 0 ] || fail 'No arguments are accepted.'
[ "$(id -u)" = 0 ] || fail 'Run this script using KernelSU root.'
for tool in getprop blockdev dd wc sha256sum cut mkdir date mv sync uname; do
  command -v "$tool" >/dev/null 2>&1 || fail "Required command is unavailable: $tool"
done
DEVICE=$(getprop ro.product.device)
case "$DEVICE" in tapas|topaz) ;; *) fail "Unexpected device: $DEVICE";; esac
SLOT_SUFFIX=$(getprop ro.boot.slot_suffix)
SLOT_NAME=$(getprop ro.boot.slot)
case "$SLOT_SUFFIX" in
  _a|_b) ;;
  '') case "$SLOT_NAME" in a|b) SLOT_SUFFIX="_$SLOT_NAME";; *) fail 'Cannot identify the active A/B slot.';; esac;;
  *) fail "Unexpected active-slot suffix: $SLOT_SUFFIX";;
esac
case "$SLOT_NAME" in
  '') ;;
  a|b) [ "$SLOT_SUFFIX" = "_$SLOT_NAME" ] || fail 'Active-slot properties disagree.';;
  *) fail "Unexpected active-slot property: $SLOT_NAME";;
esac
BLOCK=
for candidate in "/dev/block/by-name/boot$SLOT_SUFFIX" "/dev/block/bootdevice/by-name/boot$SLOT_SUFFIX"; do
  if [ -b "$candidate" ]; then BLOCK=$candidate; break; fi
done
[ -n "$BLOCK" ] || fail 'The active boot block-device alias is unavailable.'
EXPECTED=$(blockdev --getsize64 "$BLOCK") || fail 'Cannot read the boot partition size.'
case "$EXPECTED" in ''|*[!0-9]*) fail 'Invalid boot partition size.';; esac
[ "$EXPECTED" -gt 0 ] || fail 'The boot partition is empty.'
DOWNLOADS=/sdcard/Download
[ -d "$DOWNLOADS" ] && [ -w "$DOWNLOADS" ] || fail 'Unlock the phone: Download storage is unavailable.'
PARENT="$DOWNLOADS/ChatGPTKernel-backups"
mkdir -p "$PARENT" || fail 'Cannot create the backup parent directory.'
STAMP=$(date -u +%Y%m%dT%H%M%SZ) || fail 'Cannot read the date.'
BACKUP_DIR="$PARENT/manual-${STAMP}${SLOT_SUFFIX}-$$"
mkdir "$BACKUP_DIR" || fail 'Backup directory already exists or cannot be created; nothing was overwritten.'
PARTIAL="$BACKUP_DIR/boot.img.partial"
: > "$PARTIAL" || fail 'Cannot create a new backup file.'
printf 'Reading %s (%s bytes). Keep this process open until VERIFIED appears.\n' "$BLOCK" "$EXPECTED"
dd if="$BLOCK" of="$PARTIAL" bs=1048576 || fail 'Reading or saving boot failed.'
BYTES=$(wc -c < "$PARTIAL") || fail 'Cannot inspect the saved size.'
[ "$BYTES" = "$EXPECTED" ] || fail 'Incomplete saved boot image.'
SAVED_HASH=$(sha256sum "$PARTIAL" | cut -d ' ' -f 1)
SOURCE_HASH=$(sha256sum "$BLOCK" | cut -d ' ' -f 1)
[ "${#SAVED_HASH}" -eq 64 ] && [ "$SAVED_HASH" = "$SOURCE_HASH" ] || fail 'Saved boot does not match the partition SHA256.'
case "$SAVED_HASH" in *[!0-9a-f]*) fail 'Invalid SHA256 output.';; esac
[ ! -e "$BACKUP_DIR/boot.img" ] || fail 'A final image already exists; nothing was overwritten.'
mv "$PARTIAL" "$BACKUP_DIR/boot.img" || fail 'Cannot finish the backup image.'
(
  cd "$BACKUP_DIR" || exit 1
  printf '%s  boot.img\n' "$SAVED_HASH" > SHA256SUMS || exit 1
  {
    printf 'Manual backup of the running phone before kernel installation.\n'
    printf 'Device: %s\nOriginal partition: %s\nSlot: %s\nSize: %s\nSHA256: %s\n' "$DEVICE" "$BLOCK" "$SLOT_SUFFIX" "$EXPECTED" "$SAVED_HASH"
    printf 'Running kernel: '; uname -r
    printf 'ROM: '; getprop ro.build.display.id
    printf 'Created UTC: %s\n' "$STAMP"
  } > backup-info.txt || exit 1
  sha256sum -c SHA256SUMS || exit 1
) || fail 'Cannot verify the final backup files.'
sync || fail 'Cannot sync the saved backup.'
printf '\nVERIFIED: %s\nActive boot slot: %s\n' "$BACKUP_DIR" "$SLOT_SUFFIX"
printf 'Copy this entire directory to a PC or other storage, then verify SHA256SUMS there before installing.\n'
printf 'This script did not flash a partition, change a slot, or upload files.\n'
