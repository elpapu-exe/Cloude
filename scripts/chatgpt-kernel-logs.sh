#!/system/bin/sh
# ChatGPT Kernel diagnostic v6. Read-only diagnostics; one shareable text file.
# No network access, tuning, cache clearing, app closing or automatic upload.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077
DOWNLOADS=/sdcard/Download
LOCK=/data/local/tmp/chatgpt-kernel-logger.lock
INTERVAL=10

fail() { printf '%s\n' "$*" >&2; exit 1; }
read_value() {
  if [ -r "$1" ]; then cat "$1" 2>/dev/null || printf 'NA\n'; else printf 'NA\n'; fi
}
heading() { printf '\n=== %s ===\n' "$*"; }
bounded() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 6 "$@" 2>&1
  else
    printf 'Skipped: timeout command unavailable: %s\n' "$1"
    return 127
  fi
}
# Extra hardware/configuration readers have short timeouts and bounded output.
# These readers do not inspect process arguments, task lists or addresses.
detail_command() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 2 "$@" 2>/dev/null
  else
    return 127
  fi
}
detail_value() {
  if [ ! -r "$1" ]; then printf 'NA\n'; return; fi
  detail_output=$(detail_command cat "$1")
  detail_status=$?
  if [ "$detail_status" -eq 0 ]; then
    printf '%s\n' "$detail_output" | sed -n '1,8p;8q'
  else
    printf 'NA (reader exit %s)\n' "$detail_status"
  fi
}
governor_tunables() {
  active_governor=$(detail_command cat "$1/scaling_governor")
  case "$active_governor" in
    schedutil) rate_fields=rate_limit_us;;
    schedhorizon|horizon) rate_fields='up_rate_limit_us down_rate_limit_us';;
    *) printf '  active governor rate fields: NA (unlisted or unavailable governor)\n'; return;;
  esac
  for scope in "$1/$active_governor" "/sys/devices/system/cpu/cpufreq/$active_governor"; do
    printf '  active governor tunables %s:\n' "$scope"
    for rate_field in $rate_fields; do
      printf '    %s: ' "$rate_field"; detail_value "$scope/$rate_field"
    done
  done
}
gpu_configuration() {
  heading 'GPU configuration snapshots (read only; driver reports, not measured throughput)'
  for gpu_field in gpu_model gpuclk min_gpuclk max_gpuclk; do
    printf 'KGSL %s: ' "$gpu_field"; detail_value "/sys/class/kgsl/kgsl-3d0/$gpu_field"
  done
  for gpu_scope in /sys/class/kgsl/kgsl-3d0/devfreq /sys/class/devfreq/*; do
    [ -d "$gpu_scope" ] || continue
    case "$gpu_scope" in
      /sys/class/kgsl/*|*kgsl*|*gpu*|*GPU*|*3d0*) :;;
      *) continue;;
    esac
    printf '%s:\n' "$gpu_scope"
    for gpu_field in governor cur_freq min_freq max_freq available_frequencies; do
      printf '  %s: ' "$gpu_field"; detail_value "$gpu_scope/$gpu_field"
    done
  done
}
io_configuration() {
  heading "Block I/O $1 (read only; kernel device names and numeric counters only)"
  for io_device in /sys/block/sd* /sys/block/mmcblk*; do
    [ -d "$io_device" ] || continue
    printf '%s scheduler: ' "${io_device##*/}"; detail_value "$io_device/queue/scheduler"
    printf '%s hardware queue count: ' "${io_device##*/}"
    if [ -d "$io_device/mq" ]; then
      io_queue_count=0
      for io_queue in "$io_device"/mq/*; do
        [ -d "$io_queue" ] || continue
        io_queue_count=$((io_queue_count + 1))
      done
      printf '%s\n' "$io_queue_count"
    else
      printf 'NA\n'
    fi
  done
  printf 'device reads sectors_read read_ms writes sectors_written write_ms in_flight io_ms weighted_io_ms\n'
  if [ -r /proc/diskstats ]; then
    detail_command sh -c '
      rows=0
      while read -r major minor name reads merged_read sectors_read read_ms writes merged_write sectors_written write_ms in_flight io_ms weighted_ms rest; do
        rows=$((rows + 1)); [ "$rows" -le 512 ] || break
        case "$name" in
          sd*) suffix=${name#sd}; case "$suffix" in ""|*[!a-z0-9]*) continue;; esac;;
          mmcblk*) suffix=${name#mmcblk}; case "$suffix" in ""|*[!0-9p]*) continue;; esac;;
          dm-*) suffix=${name#dm-}; case "$suffix" in ""|*[!0-9]*) continue;; esac;;
          *) continue;;
        esac
        valid=1
        for number in "$reads" "$sectors_read" "$read_ms" "$writes" "$sectors_written" "$write_ms" "$in_flight" "$io_ms" "$weighted_ms"; do
          case "$number" in ""|*[!0-9]*) valid=0;; esac
        done
        [ "$valid" -eq 1 ] || continue
        printf "%s %s %s %s %s %s %s %s %s %s\n" "$name" "$reads" "$sectors_read" "$read_ms" "$writes" "$sectors_written" "$write_ms" "$in_flight" "$io_ms" "$weighted_ms"
      done < "$1"
    ' sh /proc/diskstats
  else
    printf 'NA\n'
  fi
}
runtime_hardware() {
  heading 'Driver links (read only; NA when not exposed)'
  for driver_link in /sys/devices/system/cpu/cpufreq/policy*/device/driver \
    /sys/class/kgsl/kgsl-3d0/device/driver; do
    printf '%s: ' "$driver_link"
    driver_target=$(detail_command readlink -f "$driver_link")
    if [ -n "$driver_target" ]; then printf '%s\n' "$driver_target"; else printf 'NA\n'; fi
  done
  heading 'Loaded modules (name, bytes, reference count only; max 160 entries)'
  printf 'name bytes refs\n'
  if [ -r /proc/modules ]; then
    detail_command sh -c '
      rows=0
      while read -r name bytes refs rest; do
        rows=$((rows + 1)); [ "$rows" -le 160 ] || break
        case "$name" in ""|*[!A-Za-z0-9_-]*) continue;; esac
        case "$bytes" in ""|*[!0-9]*) continue;; esac
        ref_digits=${refs#-}
        case "$ref_digits" in ""|*[!0-9]*) continue;; esac
        printf "%s %s %s\n" "$name" "$bytes" "$refs"
      done < "$1"
    ' sh /proc/modules
  else
    printf 'NA\n'
  fi
  heading 'Top-app and foreground CPU group configuration (no membership/task data)'
  for cpu_group in top-app foreground; do
    for group_file in /dev/cpuset/"$cpu_group"/cpus \
      /dev/cpuset/"$cpu_group"/effective_cpus \
      /dev/cpuctl/"$cpu_group"/cpu.uclamp.min \
      /dev/cpuctl/"$cpu_group"/cpu.uclamp.max \
      /sys/fs/cgroup/"$cpu_group"/cpuset.cpus \
      /sys/fs/cgroup/"$cpu_group"/cpuset.cpus.effective \
      /sys/fs/cgroup/"$cpu_group"/cpu.uclamp.min \
      /sys/fs/cgroup/"$cpu_group"/cpu.uclamp.max; do
      printf '%s: ' "$group_file"; detail_value "$group_file"
    done
  done
}
cleanup() {
  rm -f "$LOCK/pid" "$LOCK/bootid" "$LOCK/thermal-paths" "$LOCK/lastanr" "$LOCK/processes" "$LOCK/graphics"
  rmdir "$LOCK" 2>/dev/null
}
configuration() {
  heading 'Memory configuration (read only)'
  for file in /sys/kernel/mm/lru_gen/enabled /sys/kernel/mm/lru_gen/min_ttl_ms \
    /proc/sys/vm/swappiness /proc/sys/vm/page-cluster /proc/sys/vm/watermark_scale_factor \
    /proc/sys/vm/watermark_boost_factor \
    /proc/sys/vm/min_free_kbytes /sys/block/zram0/disksize /sys/block/zram0/comp_algorithm; do
    printf '%s: ' "$file"; read_value "$file"
  done
  cat /proc/swaps 2>/dev/null
  for extra in /sys/block/zram*; do
    [ -d "$extra" ] || continue
    [ "$extra" = /sys/block/zram0 ] && continue
    printf 'Additional zRAM device: %s\n' "$extra"
    for field in disksize comp_algorithm mm_stat; do
      printf '  %s: ' "$field"; read_value "$extra/$field"
    done
  done
  heading 'CPU policy configuration (read only; missing tunables shown as NA)'
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    printf '%s:\n' "$policy"
    for field in cpuinfo_max_freq scaling_governor scaling_min_freq scaling_max_freq; do
      printf '  %s: ' "$field"; read_value "$policy/$field"
    done
    printf '  scaling_driver: '; detail_value "$policy/scaling_driver"
    governor_tunables "$policy"
    for field in up_rate_limit_us down_rate_limit_us hispeed_load hispeed_freq rtg_boost_freq boost adaptive_low_freq adaptive_high_freq target_load_thresh target_load_shift; do
      tunable="$policy/walt/$field"
      [ -r "$tunable" ] || tunable="/sys/devices/system/cpu/cpufreq/walt/$field"
      printf '  walt/%s: ' "$field"; read_value "$tunable"
    done
  done
  for file in /sys/kernel/kprofiles/kp_mode /sys/module/kprofiles/parameters/auto_kp; do
    printf '%s: ' "$file"; read_value "$file"
  done
  gpu_configuration
  heading 'Requested display refresh preferences (not measured refresh rate)'
  for setting in min_refresh_rate peak_refresh_rate; do
    printf '%s: ' "$setting"; bounded settings get system "$setting"
  done
}
graphics() {
  heading "Graphics $1: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'Read-only HWUI counters and recent numeric frame records; no resets or window titles.\n'
  printf 'Compare counters only for the same PID and Stats since. Video surfaces may not be represented.\n'
  for package in com.zhiliaoapp.musically com.ss.android.ugc.trill com.android.systemui; do
    printf '\nPackage: %s\n' "$package"
    bounded dumpsys gfxinfo "$package" framestats > "$LOCK/graphics"
    printf 'gfxinfo exit status: %s\n' "$?"
    sed -n -E '
      /^\*\* Graphics info for pid [0-9]+ \[[A-Za-z0-9_.:]+\] \*\*$/p
      /^Stats since: [0-9]+ns$/p
      /^Total frames rendered: [0-9]+$/p
      /^Janky frames( \(legacy\))?: [0-9]+ \([0-9.]+%\)$/p
      /^[0-9]+th percentile: [0-9]+ms$/p
      /^Number [A-Za-z ]+: [0-9]+$/p
      /^No process found for: [A-Za-z0-9_.:]+$/p
      /^Flags,([A-Za-z][A-Za-z0-9]*,)*[A-Za-z0-9]*$/p
      /^[0-9]+([[:space:]]*,[[:space:]]*[0-9]+)+[[:space:]]*,?[[:space:]]*$/p
    ' "$LOCK/graphics" | sed -n '1,650p;650q'
  done
}
snapshot() {
  heading "Sample $1: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'uptime: '; read_value /proc/uptime
  grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree|CmaTotal|CmaFree|Active\(anon\)|Inactive\(anon\)|Active\(file\)|Inactive\(file\)):' /proc/meminfo
  for kind in memory cpu io; do
    printf 'PSI %s:\n' "$kind"; read_value "/proc/pressure/$kind"
  done
  printf 'CPU ticks (aggregate and per core):\n'; grep -E '^cpu([0-9]+)? ' /proc/stat
  printf 'loadavg: '; read_value /proc/loadavg
  printf 'vmstat counters:\n'
  grep -E '^(pswpin|pswpout|pgmajfault|kswapd_low_wmark_hit_quickly|kswapd_high_wmark_hit_quickly|pgscan[^ ]*|pgsteal[^ ]*|allocstall[^ ]*|workingset_refault[^ ]*|compact_(stall|fail|success)|oom_kill) ' /proc/vmstat
  printf 'zram mm_stat: '; read_value /sys/block/zram0/mm_stat
  printf 'zram io_stat: '; read_value /sys/block/zram0/io_stat
  for extra in /sys/block/zram*; do
    [ -d "$extra" ] || continue
    [ "$extra" = /sys/block/zram0 ] && continue
    printf 'Additional zRAM %s mm_stat: ' "$extra"; read_value "$extra/mm_stat"
    printf 'Additional zRAM %s io_stat: ' "$extra"; read_value "$extra/io_stat"
  done
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    printf '%s (frequency in kHz):\n' "$policy"
    for field in scaling_governor scaling_cur_freq cpuinfo_cur_freq scaling_min_freq scaling_max_freq cpuinfo_max_freq; do
      printf '  %s: ' "$field"; read_value "$policy/$field"
    done
  done
  printf 'battery temperature (tenths C): '; read_value /sys/class/power_supply/battery/temp
  printf 'battery status: '; read_value /sys/class/power_supply/battery/status
  while IFS= read -r zone; do
    printf 'thermal %s ' "$zone"; read_value "$zone/type"
    printf '  raw temperature (thermal sysfs convention: milli-C): '; read_value "$zone/temp"
  done < "$LOCK/thermal-paths"
}
processes() {
  heading 'Largest processes (CPU may be lifetime average; RSS in KiB; names only)'
  bounded ps -A -o PID,%CPU,RSS,NAME > "$LOCK/processes"
  sort -k3,3nr "$LOCK/processes" | sed -n '1,15p'
  heading 'Processes ranked by CPU percentage (same snapshot, no arguments)'
  sort -k2,2nr "$LOCK/processes" | sed -n '1,15p'
}
finish_logs() {
  graphics END
  io_configuration END
  configuration
  processes
  heading 'TikTok process memory summaries (at the end of the test)'
  for package in com.zhiliaoapp.musically com.ss.android.ugc.trill; do
    bounded dumpsys meminfo "$package" | sed -E '/^[[:space:]]*(Objects|SQL|DATABASES)([[:space:]]|$)/,$d' | sed -n '1,60p'
  done
  heading 'LMKD logs since test started (max 250 lines)'
  bounded logcat -d -T "$START_LOGCAT" -b main -b system -v threadtime \
    lowmemorykiller:I lmkd:I '*:S' | sed -n '1,250p'
  heading 'TikTok ANR and system kill events since test started (max 250 lines)'
  bounded logcat -d -T "$START_LOGCAT" -b events -v threadtime \
    am_anr:I am_kill:I '*:S' | grep -E 'am_kill|am_anr.*com\.(zhiliaoapp\.musically|ss\.android\.ugc\.trill)' | sed -n '1,250p'
  heading 'Last ANR summary (may predate this test)'
  bounded dumpsys activity lastanr > "$LOCK/lastanr"
  if sed -n '1,25p' "$LOCK/lastanr" | grep -qE '^[[:space:]]*(ANR in |Process: )com\.(zhiliaoapp\.musically|ss\.android\.ugc\.trill)([[:space:](]|$)'; then
    sed -n -E '/^[[:space:]]*(ANR time:|ANR in |Process:|PID:|UID:|Reason:|ErrorId:|Frozen:|Load:)/p' "$LOCK/lastanr" | sed -n '1,30p'
  else
    printf 'No TikTok ANR summary found; other-app contents omitted.\n'
  fi
  heading 'TikTok process section in a recent ANR trace (may be secondary; max 260 lines)'
  count=0
  for trace in $(ls -1t /data/anr/anr_* 2>/dev/null); do
    count=$((count + 1)); [ "$count" -le 3 ] || break
    modified=$(stat -c %Y "$trace" 2>/dev/null)
    case "$modified" in ''|*[!0-9]*) continue;; esac
    [ "$modified" -ge "$START_EPOCH" ] || continue
    if bounded grep -qE '^Cmd line: (com\.zhiliaoapp\.musically|com\.ss\.android\.ugc\.trill)$' "$trace"; then
      printf 'Trace: %s\n' "$trace"
      bounded sed -n -E '/^Cmd line: (com\.zhiliaoapp\.musically|com\.ss\.android\.ugc\.trill)$/,/^----- (end|pid )/{
        /^----- pid /q
        p
        /^----- end/q
      }' "$trace" | sed -n '1,260p;260q'
      break
    fi
  done
  heading 'Selected kernel errors since boot (max 100 lines)'
  bounded dmesg | grep -iE 'unknown symbol|disagrees about version|invalid module|CFI failure|kernel BUG|Oops:|out of memory|allocation failure' | tail -n 100
  heading "TEST FINISHED: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'No phone settings were changed and no files were uploaded.\n'
}

[ "$(id -u)" = 0 ] || fail 'Run with KernelSU root: su -c "sh /sdcard/Download/chatgpt-kernel-logs.sh"'

if [ "${1:-}" = --worker ]; then
  OUTPUT=$2; DURATION=$3
  exec >> "$OUTPUT" 2>&1
  trap cleanup 0
  trap 'exit 130' 1 2 15
  START_EPOCH=$(date +%s)
  START_LOGCAT=$(date '+%m-%d %H:%M:%S.000')
  heading 'ChatGPT Kernel diagnostic v6'
  printf 'Start UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
  printf 'Duration target: %s seconds; samples every %s seconds. Sleep may extend wall time.\n' "$DURATION" "$INTERVAL"
  uname -a
  printf 'Kernel build: '; read_value /proc/version
  heading 'Filesystem mounted at /data (read only)'
  CHATGPT_DATA_FILESYSTEM=
  if [ -r /proc/mounts ]; then
    while read -r source mountpoint filesystem options rest; do
      [ "$mountpoint" = /data ] || continue
      CHATGPT_DATA_FILESYSTEM=$filesystem
    done < /proc/mounts
  fi
  printf '/data filesystem: %s\n' "${CHATGPT_DATA_FILESYSTEM:-unavailable}"
  for property in ro.product.device ro.build.display.id ro.lineage.version init.svc.lmkd \
    ro.config.low_ram ro.lmk.thrashing_limit ro.lmk.thrashing_limit_critical \
    persist.device_config.lmkd_native.thrashing_limit persist.device_config.lmkd_native.thrashing_limit_critical \
    persist.device_config.lmkd_native.psi_complete_stall_ms; do
    printf '%s: ' "$property"; getprop "$property"
  done
  heading 'Relevant installed app versions'
  for package in com.zhiliaoapp.musically com.ss.android.ugc.trill com.instagram.android ps.reso.instaeclipse; do
    printf '%s:\n' "$package"
    bounded dumpsys package "$package" | grep -E 'versionName=|versionCode=|Unable to find' | sed -n '1,6p'
  done
  : > "$LOCK/thermal-paths"
  count=0
  for zone in /sys/class/thermal/thermal_zone*; do
    type=$(cat "$zone/type" 2>/dev/null)
    case "$type" in *cpu*|*CPU*|*soc*|*SOC*|*gpu*|*GPU*)
      [ "$count" -lt 6 ] || break
      printf '%s\n' "$zone" >> "$LOCK/thermal-paths"; count=$((count + 1));;
    esac
  done
  configuration
  runtime_hardware
  io_configuration BEGIN
  processes
  graphics BEGIN
  elapsed=0; sample=0
  while :; do
    snapshot "$sample"
    [ "$elapsed" -lt "$DURATION" ] || break
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL)); sample=$((sample + 1))
  done
  finish_logs
  exit 0
fi

DURATION=${1:-600}
case "$DURATION" in ''|*[!0-9]*) fail 'Duration must be an integer between 60 and 1800 seconds.';; esac
[ "$DURATION" -ge 60 ] && [ "$DURATION" -le 1800 ] || fail 'Duration must be between 60 and 1800 seconds.'
[ -d "$DOWNLOADS" ] && [ -w "$DOWNLOADS" ] || fail 'Unlock the phone: Download storage is unavailable.'
command -v nohup >/dev/null 2>&1 || fail 'This Android build has no nohup command.'
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id)
if ! mkdir "$LOCK" 2>/dev/null; then
  previous_pid=$(cat "$LOCK/pid" 2>/dev/null)
  previous_boot=$(cat "$LOCK/bootid" 2>/dev/null)
  [ -n "$previous_pid" ] || fail 'A collector is starting, or its lock is incomplete. No second collector was started.'
  case "$previous_pid" in *[!0-9]*) fail 'Invalid diagnostic lock; no processes were stopped.';; esac
  if [ "$previous_boot" = "$BOOT_ID" ] && kill -0 "$previous_pid" 2>/dev/null && \
    tr '\000' ' ' < "/proc/$previous_pid/cmdline" 2>/dev/null | grep -qE 'chatgpt-(kernel-logs|fluidez(-zram)?)\.sh'; then
    fail 'A collector is already running. Wait for its text file to finish.'
  fi
  cleanup
  mkdir "$LOCK" 2>/dev/null || fail 'Cannot acquire diagnostic lock.'
fi
trap cleanup 0
trap 'exit 130' 1 2 15
printf '%s\n' "$$" > "$LOCK/pid"
printf '%s\n' "$BOOT_ID" > "$LOCK/bootid"
OUTPUT="$DOWNLOADS/ChatGPTKernel-$(date -u '+%Y%m%d-%H%M%S')-$$.txt"
: > "$OUTPUT" || fail 'Cannot create diagnostic text file.'
nohup /system/bin/sh "$0" --worker "$OUTPUT" "$DURATION" </dev/null >> "$OUTPUT" 2>&1 &
worker_pid=$!
printf '%s\n' "$worker_pid" > "$LOCK/pid"
trap - 0 1 2 15
printf 'Collector started for %s seconds. Use TikTok normally and leave Termux in recent apps.\n' "$DURATION"
printf 'Allow %s seconds plus diagnostic overhead. Share this one text file after TEST FINISHED appears:\n%s\n' "$DURATION" "$OUTPUT"
