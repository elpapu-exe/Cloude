#!/sbin/sh
# ChatGPT Kernel: KSU-only, boot-only AnyKernel3 package.
# Backend copyright osm0sis @ xda-developers; see LICENSE.
properties() { '
kernel.string=ChatGPT Kernel 0.1.0-rc3-rebuild1 (experimental)
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=topaz
device.name2=tapas
supported.versions=13
supported.patchlevels=
supported.vendorpatchlevels=
'; }

block=boot
is_slot_device=1
slot_select=active
ramdisk_compression=auto
patch_vbmeta_flag=0
no_magisk_check=1
. tools/ak3-core.sh

case "$BLOCK" in
  */boot_a|*/boot_b) ;;
  *) abort "Unexpected target: $BLOCK. No partition was written." ;;
esac
[ -b "$BLOCK" ] || abort "Boot block device unavailable."
[ -s "$AKHOME/Image" ] || abort "Kernel image missing."

ui_print "ChatGPT Kernel 0.1.0-rc3-rebuild1: experimental, hardware untested."
ui_print "Preserving ramdisk and vendor partitions."
split_boot
. "$AKHOME/tools/chatgpt-backup.sh"
chatgpt_backup_boot
flash_boot
ui_print "Original boot saved in: $CHATGPT_BACKUP_DIR"
ui_print "Restart is required to use the new kernel."
