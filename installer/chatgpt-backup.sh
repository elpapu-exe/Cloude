#!/sbin/sh
# Save and verify the complete original boot before flash_boot can run.
chatgpt_backup_boot() {
  local backup_parent stamp bytes expected original_hash saved_hash
  bytes=$(wc -c < "$BOOTIMG")
  expected=$(blockdev --getsize64 "$BLOCK") || abort "Cannot read partition size."
  [ "$bytes" = "$expected" ] || abort "Incomplete boot dump. No partition was written."
  backup_parent=
  for location in /sdcard/Download /data/media/0/Download; do
    if [ -d "$location" ] && [ -w "$location" ]; then
      backup_parent="$location/ChatGPTKernel-backups"
      break
    fi
  done
  [ "$backup_parent" ] || abort "Unlock/decrypt internal storage to save the original boot first."
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  CHATGPT_BACKUP_DIR="$backup_parent/${stamp}${SLOT}-$$"
  (umask 077; mkdir -p "$backup_parent" && mkdir "$CHATGPT_BACKUP_DIR") || abort "Cannot create boot backup directory."
  cp "$BOOTIMG" "$CHATGPT_BACKUP_DIR/boot.img" || abort "Cannot save original boot. No partition was written."
  original_hash=$(sha256sum "$BOOTIMG" | cut -d ' ' -f 1)
  saved_hash=$(sha256sum "$CHATGPT_BACKUP_DIR/boot.img" | cut -d ' ' -f 1)
  [ -n "$original_hash" ] && [ "$original_hash" = "$saved_hash" ] || abort "Boot backup checksum mismatch."
  (
    cd "$CHATGPT_BACKUP_DIR" || exit 1
    printf '%s  boot.img\n' "$saved_hash" > SHA256SUMS
    printf 'Kernel: ChatGPT Kernel 0.1.0-rc1\nOriginal partition: %s\nSlot: %s\nSize: %s\n' "$BLOCK" "$SLOT" "$bytes" > backup-info.txt
    sha256sum -c SHA256SUMS
  ) || abort "Cannot verify saved boot backup."
  sync || abort "Cannot sync boot backup."
  ui_print "Verified original boot backup: $CHATGPT_BACKUP_DIR"
}
