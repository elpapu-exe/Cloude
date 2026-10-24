#!/system/bin/sh
# Temporary experiment, not a proven optimization. An extra 1 GiB of logical
# swap does not reserve a fixed amount of physical RAM. Restart removes it.
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
CREATED_ID=
ALLOCATION_ATTEMPTED=0
ERROR=
RESULT=

is_block_device() { [ -b "$1" ]; }
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
      /dev/block/zram[0-9]*|/dev/zram[0-9]*)
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
remove_lock_files() {
  rm -f "$LOCK/bootid" "$LOCK/pid" "$LOCK/state" "$LOCK/created_id"
  rmdir "$LOCK" 2>/dev/null
}
finish() {
  code=$?
  trap - 0 1 2 15
  if [ "$code" -ne 0 ] && [ "$OWN_LOCK" -eq 1 ]; then
    if valid_id "$CREATED_ID"; then
      swap_activity "$CREATED_ID"; activity=$?
      if [ "$activity" -eq 1 ]; then
        if printf '%s\n' "$CREATED_ID" > "$HOT_REMOVE"; then
          printf 'Removed only the newly created inactive zram%s.\n' "$CREATED_ID"
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
printf 'Temporary +1 GiB logical zRAM experiment; no performance improvement is assumed.\n'
printf 'Mode: %s\n' "$MODE"
snapshot BEFORE
package_versions
if [ "$MODE" = status ]; then RESULT='Read-only zRAM status captured.'; exit 0; fi

[ -x "$BUSYBOX" ] || die 'KernelSU BusyBox is unavailable.'
for applet in mkswap swapon; do
  "$BUSYBOX" --list 2>/dev/null | grep -qx "$applet" || die "BusyBox lacks $applet."
done
[ ! -L "$LOCK" ] || die 'Diagnostic lock is a symlink; refusing to continue.'
if [ -e "$LOCK" ]; then
  saved_boot=$(cat "$LOCK/bootid" 2>/dev/null)
  saved_state=$(cat "$LOCK/state" 2>/dev/null)
  saved_id=$(cat "$LOCK/created_id" 2>/dev/null)
  if [ "$saved_boot" = "$BOOT_ID" ] && [ "$saved_state" = active ] && valid_id "$saved_id"; then
    if swap_activity "$saved_id"; then
      RESULT='This boot already has the temporary swap device; nothing added.'
      exit 0
    fi
  fi
  die 'An existing trial lock is active or ambiguous; inspect status or restart.'
fi
[ -r /proc/swaps ] || die 'Cannot inspect active swap.'
rows=0; BASE_DEVICE=; PRIORITY=
while read -r path type size used priority rest; do
  [ "$path" = Filename ] && continue
  [ -n "$path" ] || continue
  rows=$((rows + 1)); BASE_DEVICE=$path; PRIORITY=$priority
done < /proc/swaps
[ "$rows" -eq 1 ] || die 'Exactly one active swap device (zram0) is required.'
case "$BASE_DEVICE" in /dev/block/zram0|/dev/zram0) ;; *) die 'The active swap is not the expected zram0.';; esac
swap_activity 0 || die 'Cannot validate the active zram0 entry.'
[ "$(cat /sys/block/zram0/disksize 2>/dev/null)" = 2147483648 ] || die 'zram0 must have exactly 2 GiB logical capacity.'
is_block_device "$BASE_DEVICE" && node_matches_sysfs "$BASE_DEVICE" /sys/block/zram0 || die 'zram0 block-device identity does not match sysfs.'
case "$PRIORITY" in ''|*[!0-9]*) die 'Existing swap priority must be explicit and nonnegative.';; esac
[ "$PRIORITY" -le 32767 ] || die 'Swap priority is outside the supported range.'
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
printf '%s\n' "$COMPRESSOR" > "$NEW_SYS/comp_algorithm" || die 'Cannot select the copied compressor.'
[ "$(current_compressor "$NEW_SYS/comp_algorithm")" = "$COMPRESSOR" ] || die 'New compressor readback differs from zram0.'
printf '1073741824\n' > "$NEW_SYS/disksize" || die 'Cannot set the new 1 GiB logical capacity.'
[ "$(cat "$NEW_SYS/disksize" 2>/dev/null)" = 1073741824 ] || die 'New logical capacity readback is invalid.'
waited=0
while ! is_block_device "$NEW_DEVICE"; do
  [ "$waited" -lt 5 ] || die 'New block-device node did not appear within five seconds.'
  sleep 1; waited=$((waited + 1))
done
node_matches_sysfs "$NEW_DEVICE" "$NEW_SYS" || die 'New block-device identity does not match sysfs.'
printf 'Selected new device: zram%s; compressor: %s; priority: %s.\n' "$CREATED_ID" "$COMPRESSOR" "$PRIORITY"
"$BUSYBOX" mkswap "$NEW_DEVICE" || die 'mkswap failed on the new device.'
printf 'activating\n' > "$LOCK/state" || die 'Cannot record activation state.'
"$BUSYBOX" swapon -p "$PRIORITY" "$NEW_DEVICE" || die 'swapon reported an error; active new swap will be left intact.'
swap_activity "$CREATED_ID" || die 'Activation could not be confirmed; the new device will not be forcibly removed.'
printf 'active\n' > "$LOCK/state" || die 'Swap is active but its state could not be recorded.'
snapshot AFTER
RESULT='Temporary +1 GiB logical swap is active until restart. It does not reserve a fixed amount of physical RAM.'
exit 0
