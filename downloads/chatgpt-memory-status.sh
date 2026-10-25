#!/system/bin/sh
# Read-only snapshot. Does not provoke OOM or change phone settings.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077
BUSYBOX=/data/adb/ksu/bin/busybox
DOWNLOADS=/sdcard/Download
TEMP=
REPORT=

cleanup() {
  code=$?
  trap - 0 1 2 15
  if [ -n "$TEMP" ]; then
    rm -f "$TEMP/kernel" "$TEMP/kernel-error" "$TEMP/logcat" "$TEMP/logcat-error"
    rmdir "$TEMP" 2>/dev/null
  fi
  [ -z "$REPORT" ] || printf 'Report: %s\n' "$REPORT" >&3
  exit "$code"
}
read_value() {
  if [ -r "$1" ]; then cat "$1" 2>/dev/null || printf 'Read failed.\n'; else printf 'Unavailable.\n'; fi
}
parse_kernel() {
  "$BUSYBOX" awk '
function keep() {
  if (block != "") { blocks++; saved[blocks % 2] = block; block = ""; }
}
{
  if (match($0, /^\[[[:space:]]*[0-9]+(\.[0-9]+)?\]/)) {
    stamp = substr($0, RSTART, RLENGTH); gsub(/[^0-9.]/, "", stamp);
    if (first == "") first = stamp;
    last = stamp;
  }
}
/invoked oom-killer/ { keep(); active = 1; tasks = 0; lines = 0; headers++; }
/Tasks state/ { if (active) tasks = 1; }
{
  summary = ($0 ~ /oom-kill:|Out of memory:|Memory cgroup out of memory:/);
  killed = ($0 ~ /Killed process/ && $0 ~ /[Oo]ut of memory/);
  if (!active && (summary || killed)) { active = 1; tasks = 1; lines = 0; }
  if (active && ((!tasks && lines++ < 100) || summary || killed)) block = block $0 "\n";
  if (killed) { kills++; keep(); active = 0; }
}
END {
  keep();
  print "Lines read:", NR;
  print "First kernel timestamp:", (first == "" ? "unavailable" : first);
  print "Last kernel timestamp:", (last == "" ? "unavailable" : last);
  print "OOM headers:", headers + 0, "kill summaries:", kills + 0, "captured blocks:", blocks + 0;
  if (!blocks) print "No matching OOM context remains in this source.";
  start = blocks > 1 ? blocks - 1 : 1;
  for (i = start; i <= blocks; i++) {
    print "--- OOM block", i, "(last two only; task table omitted) ---";
    printf "%s", saved[i % 2];
  }
}' "$1"
}

[ "$(id -u)" = 0 ] || { printf 'Run with KernelSU root.\n' >&2; exit 1; }
[ -d "$DOWNLOADS" ] && [ -w "$DOWNLOADS" ] || { printf 'Download storage is unavailable.\n' >&2; exit 1; }
REPORT="$DOWNLOADS/ChatGPTKernel-memoria-$(date -u '+%Y%m%d-%H%M%S')-$$.txt"
exec 3>&1
: > "$REPORT" || { printf 'Cannot create report.\n' >&2; exit 1; }
exec >> "$REPORT" 2>&1
trap cleanup 0
trap 'exit 130' 1 2 15
printf '=== Read-only memory and kernel-log snapshot v1 ===\n'
printf 'UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
printf 'uptime: '; read_value /proc/uptime
printf 'boot ID: '; read_value /proc/sys/kernel/random/boot_id
printf 'kernel: '; uname -r
printf '\n=== Current memory (does not reconstruct past OOM conditions) ===\n'
read_value /proc/meminfo
printf '\nActive swap:\n'; read_value /proc/swaps
printf '\nMemory PSI:\n'; read_value /proc/pressure/memory
for field in min_free_kbytes watermark_scale_factor swappiness page-cluster oom_dump_tasks oom_kill_allocating_task overcommit_memory; do
  printf '%s: ' "$field"; read_value "/proc/sys/vm/$field"
done
printf '\nBuddy allocator:\n'; read_value /proc/buddyinfo
printf '\nMemory zones:\n'; read_value /proc/zoneinfo
printf '\nSelected memory counters:\n'
grep -E '^(oom_kill|allocstall_|pgscan_|pgsteal_|pswpin |pswpout |compact_)' /proc/vmstat
printf '\n=== Existing kernel OOM context ===\n'
[ -x "$BUSYBOX" ] && "$BUSYBOX" --list 2>/dev/null | grep -qx awk \
  || { printf 'KernelSU BusyBox awk unavailable; kernel log not read.\n'; exit 1; }
TEMP=$(mktemp -d /data/local/tmp/chatgpt-memory-XXXXXX) \
  || { printf 'Cannot create private diagnostic directory.\n'; exit 1; }
dmesg > "$TEMP/kernel" 2> "$TEMP/kernel-error"
status=$?
printf 'dmesg exit status: %s\n' "$status"
printf 'dmesg error output (up to six lines):\n'
sed -n '1,6p' "$TEMP/kernel-error"
if [ "$status" -eq 0 ]; then
  parse_kernel "$TEMP/kernel"
  printf 'dmesg parser exit status: %s\n' "$?"
else
  printf 'Kernel buffer could not be read.\n'
fi
# A second existing source may retain messages no longer present in dmesg.
# It is filtered before sharing; no general application logcat is collected.
printf '\nKernel logcat fallback:\n'
if command -v timeout >/dev/null 2>&1; then
  timeout 5 logcat -d -b kernel -v monotonic > "$TEMP/logcat" 2> "$TEMP/logcat-error"
  status=$?
  printf 'kernel logcat exit status: %s\n' "$status"
  sed -n '1,6p' "$TEMP/logcat-error"
  if [ "$status" -eq 0 ]; then
    parse_kernel "$TEMP/logcat"
    printf 'kernel logcat parser exit status: %s\n' "$?"
  else
    printf 'Kernel logcat source unavailable.\n'
  fi
else
  printf 'Skipped: bounded logcat reader unavailable.\n'
fi
printf '\n=== SNAPSHOT FINISHED ===\n'
printf 'No settings changed. No allocation test or stress test was run. No data was uploaded.\n'
