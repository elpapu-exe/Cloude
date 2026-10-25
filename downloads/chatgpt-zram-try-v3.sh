#!/system/bin/sh
# Temporary experiment, not a proven optimization. Adds up to 1 GiB logical
# swap toward a 3 GiB total. It does not reserve that amount of physical RAM.
# Restart removes the added device.
# Existing swap, apps, modules, CPU, thermal and lmkd settings are not changed.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077
BUSYBOX=/data/adb/ksu/bin/busybox
DOWNLOADS=/sdcard/Download
LOCK=
HOT_ADD=/sys/class/zram-control/hot_add
HOT_REMOVE=/sys/class/zram-control/hot_remove
MODE=${1:-apply}
OWN_LOCK=0
OWN_GATE=0
CREATED_ID=
ALLOCATION_ATTEMPTED=0
ERROR=
RESULT=
RECOVERY_REASON=

is_block_device() { [ -b "$1" ]; }
# Android Toybox printf is unbuffered: a literal newline in the format can be
# a separate sysfs store. Use one short string conversion, with no literal tail.
write_sysfs() { printf '%s' "$2" > "$1"; }
read_value() {
  if [ -r "$1" ]; then cat "$1" 2>/dev/null || printf 'NA\n'; else printf 'NA\n'; fi
}
die() { ERROR=$*; printf 'ERROR: %s\n' "$ERROR" >&2; exit 1; }
valid_id() {
  case "$1" in [1-9]|[1-5][0-9]|6[0-3]) return 0;; *) return 1;; esac
}
current_compressor() { cat "$1" 2>/dev/null | sed -n 's/.*\[\([^]]*\)\].*/\1/p'; }
meminfo_value() {
  while read -r key value rest; do
    [ "$key" = "$1:" ] && { printf '%s\n' "$value"; return 0; }
  done < /proc/meminfo
  return 1
}
# Return 0 for active, 1 for confirmed inactive, 2 for unreadable/ambiguous.
swap_activity() {
  [ -r /proc/swaps ] || return 2
  seen_header=0; seen_active=0; ambiguous=0
  while read -r path type size used priority rest; do
    [ -n "$path" ] || continue
    if [ "$path" = Filename ]; then seen_header=1; continue; fi
    case "$size:$used" in *[!0-9:]*|:*|*:) ambiguous=1; continue;; esac
    case "$path" in
      /dev/block/zram[0-9]*|/dev/zram[0-9]*|/block/zram[0-9]*)
        number=${path##*/zram}
        case "$number" in ''|*[!0-9]*) ambiguous=1; continue;; esac
        [ "$number" = "$1" ] && seen_active=1;;
      *) ambiguous=1;;
    esac
  done < /proc/swaps
  [ "$seen_header" -eq 1 ] || return 2
  [ "$seen_active" -eq 0 ] || return 0
  [ "$ambiguous" -eq 0 ] || return 2
  return 1
}
node_matches_sysfs() {
  node=$(stat -L -c '%t:%T' "$1" 2>/dev/null) || return 1
  case "$node" in ''|*[!0-9a-fA-F:]*|:*|*:) return 1;; esac
  major_hex=${node%:*}; minor_hex=${node#*:}
  [ "$((0x$major_hex)):$((0x$minor_hex))" = "$(cat "$2/dev" 2>/dev/null)" ]
}
resolve_base_device() {
  # /proc/swaps uses the mount view of its reader. /block/zram0 may name
  # the same device exposed to this shell as /dev/block/zram0.
  if [ -e "$BASE_SWAP_PATH" ] || [ -L "$BASE_SWAP_PATH" ]; then
    is_block_device "$BASE_SWAP_PATH" \
      && node_matches_sysfs "$BASE_SWAP_PATH" /sys/block/zram0 || return 1
    BASE_DEVICE=$BASE_SWAP_PATH
    return 0
  fi
  [ "$BASE_SWAP_PATH" = /block/zram0 ] || return 1
  for base_node in /dev/block/zram0 /dev/zram0; do
    if is_block_device "$base_node" && node_matches_sysfs "$base_node" /sys/block/zram0; then
      BASE_DEVICE=$base_node
      return 0
    fi
  done
  return 1
}
base_state_unchanged() {
  [ "$(cat /sys/block/zram0/disksize 2>/dev/null)" = "$BASE_BYTES" ] || return 1
  only_base_swap || return 1
  while read -r path type size used priority rest; do
    [ -n "$path" ] && [ "$path" != Filename ] || continue
    [ "$path" = "$BASE_SWAP_PATH" ] && [ "$type" = partition ] \
      && [ "$size" = "$BASE_SWAP_SIZE" ] && [ "$priority" = "$PRIORITY" ] || return 1
  done < /proc/swaps
  is_block_device "$BASE_DEVICE" && node_matches_sysfs "$BASE_DEVICE" /sys/block/zram0
}
remove_lock_files() {
  rm -f "$LOCK/bootid" "$LOCK/pid" "$LOCK/state" "$LOCK/created_id"
  rmdir "$LOCK" 2>/dev/null
}
device_absent() {
  [ ! -e "/sys/block/zram$1" ] && [ ! -L "/sys/block/zram$1" ] \
    && [ ! -e "/sys/devices/virtual/block/zram$1" ] \
    && [ ! -L "/sys/devices/virtual/block/zram$1" ]
}
only_base_zram() {
  for candidate in /sys/block/zram*; do
    [ -e "$candidate" ] || [ -L "$candidate" ] || continue
    [ "$candidate" = /sys/block/zram0 ] || return 1
  done
  [ -d /sys/block/zram0 ]
}
only_base_swap() {
  [ -r /proc/swaps ] || return 1
  base_rows=0; base_header=0
  while read -r path type size used priority rest; do
    [ -n "$path" ] || continue
    if [ "$path" = Filename ]; then base_header=1; continue; fi
    case "$path" in /dev/block/zram0|/dev/zram0|/block/zram0) ;; *) return 1;; esac
    [ "$type" = partition ] || return 1
    case "$size:$used" in *[!0-9:]*|:*|*:) return 1;; esac
    base_rows=$((base_rows + 1))
  done < /proc/swaps
  [ "$base_header" -eq 1 ] && [ "$base_rows" -eq 1 ]
}
# Recover only a dead, same-boot allocation whose new device has disappeared.
# Never adopt, reconfigure or remove a device from an earlier execution.
recover_abandoned_lock() {
  RECOVERY_REASON='saved boot, state or device ID does not match an abandoned allocation'
  [ "$saved_boot" = "$BOOT_ID" ] && [ "$saved_state" = allocating ] \
    && valid_id "$saved_id" || return 1
  RECOVERY_REASON='saved metadata is incomplete or contains a symlink'
  for field in bootid pid state created_id; do
    [ -f "$LOCK/$field" ] && [ ! -L "$LOCK/$field" ] || return 1
  done
  saved_pid=$(cat "$LOCK/pid" 2>/dev/null)
  RECOVERY_REASON='previous PID is invalid'
  case "$saved_pid" in ''|0|0*|*[!0-9]*) return 1;; esac
  RECOVERY_REASON='previous PID still exists or process visibility cannot be confirmed'
  [ -d "/proc/$$" ] && [ ! -d "/proc/$saved_pid" ] || return 1
  kill -0 "$saved_pid" 2>/dev/null && return 1
  RECOVERY_REASON='previous extra zRAM device is still present'
  device_absent "$saved_id" || return 1
  RECOVERY_REASON='an additional zRAM device is present'
  only_base_zram || return 1
  RECOVERY_REASON='active swap is not exclusively a recognized zram0 partition'
  only_base_swap || return 1
  RECOVERY_REASON='previous extra swap is active or its inactivity is ambiguous'
  swap_activity "$saved_id"; [ "$?" -eq 1 ] || return 1
  # Keep the old metadata for diagnosis instead of deleting it. A competing
  # execution still must acquire the canonical lock with mkdir below.
  archived_lock="$LOCK.previous-$$"
  RECOVERY_REASON='could not reserve an archive for the previous lock'
  mkdir "$archived_lock" 2>/dev/null || return 1
  RECOVERY_REASON='could not archive the previous lock'
  mv "$LOCK" "$archived_lock/metadata" || return 1
  printf 'Archived a dead allocation lock: its new device no longer exists.\n'
}
finish() {
  code=$?
  trap - 0 1 2 15
  if [ "$code" -ne 0 ] && [ "$OWN_LOCK" -eq 1 ]; then
    if valid_id "$CREATED_ID"; then
      swap_activity "$CREATED_ID"; activity=$?
      if [ "$activity" -eq 1 ]; then
        if device_absent "$CREATED_ID" \
          || { write_sysfs "$HOT_REMOVE" "$CREATED_ID" && device_absent "$CREATED_ID"; }; then
          printf 'Confirmed newly created inactive zram%s is absent.\n' "$CREATED_ID"
          CREATED_ID=; ALLOCATION_ATTEMPTED=0
        else
          printf 'New-device removal failed; retained state for inspection/restart.\n'
        fi
      else
        printf 'New swap is active or its inactivity cannot be proved; left intact. Restart to remove it.\n'
      fi
    fi
    if [ "$ALLOCATION_ATTEMPTED" -eq 0 ]; then remove_lock_files; fi
  fi
  if [ "$code" -ne 0 ]; then snapshot AFTER_FAILURE; fi
  if [ "$OWN_GATE" -eq 1 ]; then rmdir "$GATE" 2>/dev/null; fi
  printf '\nReport finished. Exit status: %s\n' "$code"
  if [ "$code" -eq 0 ]; then
    printf '%s\nReport: %s\n' "$RESULT" "$REPORT" >&3
  else
    printf 'Error: %s\nReport: %s\n' "${ERROR:-Interrupted or incomplete diagnostic}" "$REPORT" >&4
  fi
  exit "$code"
}
snapshot() {
  printf '\n=== %s: %s ===\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'uptime: '; read_value /proc/uptime
  grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
  printf 'Memory PSI:\n'; read_value /proc/pressure/memory
  printf 'Active swap:\n'; read_value /proc/swaps
  for zram in /sys/block/zram*; do
    [ -d "$zram" ] || continue
    printf '%s:\n' "$zram"
    for field in dev disksize comp_algorithm mm_stat; do
      printf '  %s: ' "$field"; read_value "$zram/$field"
    done
  done
  for property in ro.config.low_ram \
    persist.device_config.lmkd_native.thrashing_limit \
    persist.device_config.lmkd_native.thrashing_limit_critical \
    persist.device_config.lmkd_native.psi_complete_stall_ms \
    ro.lmk.thrashing_limit ro.lmk.thrashing_limit_critical ro.lmk.psi_complete_stall_ms; do
    printf '%s: ' "$property"; getprop "$property"
  done
  printf 'Trial lock:\n'
  for field in bootid pid state created_id; do
    printf '  %s: ' "$field"; read_value "$LOCK/$field"
  done
}
package_versions() {
  printf '\n=== Selected app versions (no app content) ===\n'
  for package in com.instagram.android ps.reso.instaeclipse; do
    printf '%s:\n' "$package"
    if command -v timeout >/dev/null 2>&1; then
      timeout 4 dumpsys package "$package" 2>/dev/null \
        | grep -E '^[[:space:]]*version(Name|Code)=' | sed -n '1,4p;4q'
    else
      printf 'Skipped: timeout unavailable.\n'
    fi
  done
}

[ "$(id -u)" = 0 ] || { printf 'Run with KernelSU root.\n' >&2; exit 1; }
case "$MODE" in apply|status) ;; *) printf 'Usage: sh chatgpt-zram-try.sh [apply|status]\n' >&2; exit 1;; esac
[ "$#" -le 1 ] || { printf 'Only one mode argument is accepted.\n' >&2; exit 1; }
[ "$(getprop ro.product.device)" = tapas ] || { printf 'This experiment requires device tapas.\n' >&2; exit 1; }
[ "$(getprop ro.build.version.sdk)" = 33 ] || { printf 'This experiment requires Android API 33.\n' >&2; exit 1; }
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
case "$BOOT_ID" in ''|*[!0-9a-zA-Z-]*) printf 'Cannot validate the current boot ID.\n' >&2; exit 1;; esac
LOCK=/data/local/tmp/chatgpt-zram-try-$BOOT_ID.lock
GATE="$LOCK.apply"
[ ! -L "$LOCK" ] || { printf 'Diagnostic lock is a symlink; refusing to inspect it.\n' >&2; exit 1; }
if [ -e "$LOCK" ]; then
  [ -d "$LOCK" ] && [ "$(stat -c '%u' "$LOCK" 2>/dev/null)" = 0 ] \
    && [ "$(stat -c '%a' "$LOCK" 2>/dev/null)" = 700 ] \
    || { printf 'Diagnostic lock must be a private root-owned directory.\n' >&2; exit 1; }
fi
[ -d "$DOWNLOADS" ] && [ -w "$DOWNLOADS" ] || { printf 'Unlock the phone: Download storage is unavailable.\n' >&2; exit 1; }
REPORT="$DOWNLOADS/ChatGPTKernel-zRAM-$(date -u '+%Y%m%d-%H%M%S')-$$.txt"
exec 3>&1 4>&2
: > "$REPORT" || { printf 'Cannot create report.\n' >&4; exit 1; }
exec >> "$REPORT" 2>&1
trap finish 0
trap 'ERROR="Interrupted"; exit 130' 1 2 15
printf 'Temporary logical zRAM experiment toward 3 GiB total; no performance improvement is assumed.\n'
printf 'Script revision: 3 (mount aliases, existing size and automatic priority).\n'
printf 'Mode: %s\n' "$MODE"
if [ "$MODE" = apply ]; then
  # Serialize the entire apply, including archival of an older failed lock.
  # A killed process may leave this empty gate behind: fail closed, never steal.
  mkdir "$GATE" 2>/dev/null || die 'Another apply is running or left an incomplete operation; inspect status or restart.'
  OWN_GATE=1
fi
snapshot BEFORE
package_versions
if [ "$MODE" = status ]; then RESULT='Read-only zRAM status captured.'; exit 0; fi

[ -x "$BUSYBOX" ] || die 'KernelSU BusyBox is unavailable.'
for applet in awk mkswap swapon; do
  "$BUSYBOX" --list 2>/dev/null | grep -qx "$applet" || die "BusyBox lacks $applet."
done
[ ! -L "$LOCK" ] || die 'Diagnostic lock is a symlink; refusing to continue.'
if [ -e "$LOCK" ]; then
  for field in bootid pid state created_id; do
    [ ! -L "$LOCK/$field" ] || die 'Trial metadata contains a symlink; refusing to continue.'
  done
  saved_boot=$(cat "$LOCK/bootid" 2>/dev/null)
  saved_state=$(cat "$LOCK/state" 2>/dev/null)
  saved_id=$(cat "$LOCK/created_id" 2>/dev/null)
  if [ "$saved_boot" = "$BOOT_ID" ] && [ "$saved_state" = active ] && valid_id "$saved_id"; then
    if swap_activity "$saved_id"; then
      RESULT='This boot already has the temporary swap device; nothing added.'
      exit 0
    fi
  fi
  recover_abandoned_lock || die "Existing trial lock: $RECOVERY_REASON; no swap device changed."
fi
[ -r /proc/swaps ] || die 'Cannot inspect active swap.'
rows=0; BASE_DEVICE=; BASE_SWAP_PATH=; PRIORITY=
while read -r path type size used priority rest; do
  [ "$path" = Filename ] && continue
  [ -n "$path" ] || continue
  rows=$((rows + 1)); BASE_SWAP_PATH=$path; BASE_SWAP_SIZE=$size
  BASE_SWAP_TYPE=$type; PRIORITY=$priority
done < /proc/swaps
[ "$rows" -eq 1 ] || die 'Exactly one active swap device (zram0) is required.'
case "$BASE_SWAP_PATH" in /dev/block/zram0|/dev/zram0|/block/zram0) ;; *) die 'The active swap is not the expected zram0.';; esac
[ "$BASE_SWAP_TYPE" = partition ] || die 'The active zram0 swap must be a partition.'
swap_activity 0 || die 'Cannot validate the active zram0 entry.'
resolve_base_device || die 'zram0 block-device identity does not match sysfs.'
BASE_BYTES=$(cat /sys/block/zram0/disksize 2>/dev/null)
case "$BASE_BYTES" in ''|*[!0-9]*) die 'Cannot read the existing zRAM capacity.';; esac
# Android mksh arithmetic is signed 32-bit. Let BusyBox awk validate/compute
# large byte counts; the increment is at most 1 GiB and fits the shell.
SIZES=$("$BUSYBOX" awk -v current="$BASE_BYTES" 'BEGIN {
  if (current < 2147483648 || current >= 3221225472 || current % 4096 != 0) exit 1;
  printf "%.0f %.0f\n", 3221225472-current, current/1024-4;
}') || die 'Existing zRAM must be at least 2 GiB and below 3 GiB, with 4 KiB alignment.'
NEW_BYTES=${SIZES%% *}; EXPECTED_SWAP_KIB=${SIZES#* }
[ "$BASE_SWAP_SIZE" = "$EXPECTED_SWAP_KIB" ] || die 'Active swap size does not match the zram0 capacity and 4 KiB swap header.'
case "$PRIORITY" in -*) AUTO_PRIORITY=1; PRIORITY_NUMBER=${PRIORITY#-};; *) AUTO_PRIORITY=0; PRIORITY_NUMBER=$PRIORITY;; esac
case "$PRIORITY_NUMBER" in ''|*[!0-9]*) die 'Existing swap priority is invalid.';; esac
[ "${#PRIORITY_NUMBER}" -le 5 ] && [ "$PRIORITY_NUMBER" -le 32767 ] || die 'Swap priority is outside the supported range.'
AVAILABLE=$(meminfo_value MemAvailable)
case "$AVAILABLE" in ''|*[!0-9]*) die 'Cannot read MemAvailable.';; esac
[ "$AVAILABLE" -ge 524288 ] || die 'At least 512 MiB MemAvailable is required before this experiment.'
COMPRESSOR=$(current_compressor /sys/block/zram0/comp_algorithm)
case "$COMPRESSOR" in lzo|lzo-rle|lz4|lz4hc|lz4kd|zstd|842) ;; *) die 'The selected zram0 compressor is unknown; refusing to guess.';; esac
[ -r "$HOT_ADD" ] && [ -w "$HOT_REMOVE" ] || die 'Dynamic zRAM control is unavailable.'
BEFORE_IDS=' '
for zram in /sys/block/zram*; do
  [ -d "$zram" ] || continue
  BEFORE_IDS="$BEFORE_IDS${zram##*/zram} "
done
base_state_unchanged || die 'The original swap configuration changed during preflight; nothing allocated.'
mkdir "$LOCK" 2>/dev/null || die 'Another trial acquired the lock.'
OWN_LOCK=1
printf '%s\n' "$BOOT_ID" > "$LOCK/bootid" || die 'Cannot record trial ownership.'
printf '%s\n' "$$" > "$LOCK/pid" || die 'Cannot record trial PID.'
printf 'allocating\n' > "$LOCK/state" || die 'Cannot record trial state.'
# Reading hot_add creates a device. This is its only read in the script.
ALLOCATION_ATTEMPTED=1
new_id=$(cat "$HOT_ADD") || die 'zRAM allocation failed; inspect status before retrying.'
valid_id "$new_id" || die 'Allocation returned an unexpected ID; no device will be removed.'
case "$BEFORE_IDS" in *" $new_id "*) die 'Returned ID existed before allocation; refusing to touch it.';; esac
CREATED_ID=$new_id
printf '%s\n' "$CREATED_ID" > "$LOCK/created_id" || die 'Cannot record the newly created device.'
NEW_SYS=/sys/block/zram$CREATED_ID
NEW_DEVICE=/dev/block/zram$CREATED_ID
[ -d "$NEW_SYS" ] || die 'New zRAM sysfs directory is missing.'
[ "$(cat "$NEW_SYS/disksize" 2>/dev/null)" = 0 ] || die 'New device was already initialized; refusing to configure it.'
swap_activity "$CREATED_ID"; [ "$?" -eq 1 ] || die 'New device inactivity cannot be confirmed.'
if [ "$(current_compressor "$NEW_SYS/comp_algorithm")" != "$COMPRESSOR" ]; then
  write_sysfs "$NEW_SYS/comp_algorithm" "$COMPRESSOR" || die 'Cannot select the copied compressor.'
fi
[ "$(current_compressor "$NEW_SYS/comp_algorithm")" = "$COMPRESSOR" ] || die 'New compressor readback differs from zram0.'
write_sysfs "$NEW_SYS/disksize" "$NEW_BYTES" || die 'Cannot set the new logical capacity.'
[ "$(cat "$NEW_SYS/disksize" 2>/dev/null)" = "$NEW_BYTES" ] || die 'New logical capacity readback is invalid.'
waited=0
while ! is_block_device "$NEW_DEVICE"; do
  [ "$waited" -lt 5 ] || die 'New block-device node did not appear within five seconds.'
  sleep 1; waited=$((waited + 1))
done
node_matches_sysfs "$NEW_DEVICE" "$NEW_SYS" || die 'New block-device identity does not match sysfs.'
printf 'Selected new device: zram%s; capacity: %s bytes; compressor: %s; base priority: %s.\n' "$CREATED_ID" "$NEW_BYTES" "$COMPRESSOR" "$PRIORITY"
"$BUSYBOX" mkswap "$NEW_DEVICE" || die 'mkswap failed on the new device.'
printf 'activating\n' > "$LOCK/state" || die 'Cannot record activation state.'
if [ "$AUTO_PRIORITY" -eq 1 ]; then
  "$BUSYBOX" swapon "$NEW_DEVICE" || die 'swapon reported an error; active new swap will be left intact.'
else
  "$BUSYBOX" swapon -p "$PRIORITY" "$NEW_DEVICE" || die 'swapon reported an error; active new swap will be left intact.'
fi
swap_activity "$CREATED_ID" || die 'Activation could not be confirmed; the new device will not be forcibly removed.'
printf 'active\n' > "$LOCK/state" || die 'Swap is active but its state could not be recorded.'
snapshot AFTER
RESULT="Temporary $((NEW_BYTES / 1048576)) MiB logical swap is active until restart; target total 3 GiB. It does not reserve a fixed amount of physical RAM."
exit 0
