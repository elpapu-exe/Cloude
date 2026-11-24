### AnyKernel3 Script - Tapas / Topaz (GKI Safe: preserva modulos vendor Goodix/WiFi)
## osm0sis @ xda-developers

properties() { '
kernel.string=CloudeOpt Kernel (Tapas/Topaz GKI 5.15 - MGLRU + SSG + BBRv3)
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=topaz
device.name2=tapas
supported.versions=13-17
supported.patchlevels=
supported.vendorpatchlevels=
'; }

block=boot
is_slot_device=auto
ramdisk_compression=auto
patch_vbmeta_flag=auto
no_magisk_check=1

. tools/ak3-core.sh

if [ -L "/dev/block/bootdevice/by-name/init_boot_a" ] || [ -L "/dev/block/by-name/init_boot_a" ]; then
  split_boot
  flash_boot
else
  dump_boot
  write_boot
fi
