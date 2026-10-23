#!/system/bin/sh
# ChatGPT Kernel diagnostic v2. Read-only diagnostics; one shareable text file.
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
cleanup() {
  rm -f "$LOCK/pid" "$LOCK/bootid" "$LOCK/thermal-paths" "$LOCK/lastanr" "$LOCK/processes"
  rmdir "$LOCK" 2>/dev/null
}
configuration() {
  heading 'Memory configuration (read only)'
  for file in /sys/kernel/mm/lru_gen/enabled /sys/kernel/mm/lru_gen/min_ttl_ms \
    /proc/sys/vm/swappiness /proc/sys/vm/page-cluster /proc/sys/vm/watermark_scale_factor \
    /proc/sys/vm/min_free_kbytes /sys/block/zram0/disksize /sys/block/zram0/comp_algorithm; do
    printf '%s: ' "$file"; read_value "$file"
  done
  cat /proc/swaps 2>/dev/null
}
snapshot() {
  heading "Sample $1: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'uptime: '; read_value /proc/uptime
  grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree|Active\(anon\)|Inactive\(anon\)|Active\(file\)|Inactive\(file\)):' /proc/meminfo
  for kind in memory cpu io; do
    printf 'PSI %s:\n' "$kind"; read_value "/proc/pressure/$kind"
  done
  printf 'CPU ticks: '; grep '^cpu ' /proc/stat
  printf 'loadavg: '; read_value /proc/loadavg
  printf 'vmstat counters:\n'
  grep -E '^(pswpin|pswpout|pgmajfault|pgscan[^ ]*|pgsteal[^ ]*|allocstall[^ ]*|workingset_refault[^ ]*|compact_(stall|fail|success)|oom_kill) ' /proc/vmstat
  printf 'zram mm_stat: '; read_value /sys/block/zram0/mm_stat
  printf 'zram io_stat: '; read_value /sys/block/zram0/io_stat
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    printf '%s (frequency in kHz):\n' "$policy"
    for field in scaling_governor scaling_cur_freq cpuinfo_cur_freq scaling_min_freq scaling_max_freq; do
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
      bounded sed -n -E '/^Cmd line: (com\.zhiliaoapp\.musically|com\.ss\.android\.ugc\.trill)$/,/^----- end/p' "$trace" | sed -n '1,260p'
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
  heading 'ChatGPT Kernel diagnostic v2'
  printf 'Start UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
  printf 'Duration target: %s seconds; samples every %s seconds. Sleep may extend wall time.\n' "$DURATION" "$INTERVAL"
  uname -a
  printf 'Kernel build: '; read_value /proc/version
  for property in ro.product.device ro.build.display.id ro.lineage.version init.svc.lmkd; do
    printf '%s: ' "$property"; getprop "$property"
  done
  heading 'TikTok installed versions'
  for package in com.zhiliaoapp.musically com.ss.android.ugc.trill; do
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
  processes
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
    tr '\000' ' ' < "/proc/$previous_pid/cmdline" 2>/dev/null | grep -qF 'chatgpt-kernel-logs.sh'; then
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
printf 'Share this one text file after it ends (allow 10-12 minutes):\n%s\n' "$OUTPUT"
