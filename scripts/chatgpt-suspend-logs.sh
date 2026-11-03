#!/system/bin/sh
# ChatGPT Reposo diagnostic v1: two snapshots, no process between them.
# Reads only system interfaces. Writes only its private state and a Download TXT.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077
STATE=/data/adb/chatgpt-reposo-diagnostico
DOWNLOADS=/sdcard/Download

fail() { printf '%s\n' "$*" >&2; exit 1; }
heading() { printf '\n=== %s ===\n' "$*"; }
limited() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 4 "$@" 2>&1
  else
    printf 'NA: timeout unavailable; command skipped: %s\n' "$1"
    return 127
  fi
}
value() {
  printf '%s: ' "$1"
  if [ -r "$1" ]; then limited cat "$1" | sed -n '1,8p;8q'; else printf 'NA\n'; fi
}
table() {
  heading "$1 (cumulative; availability depends on kernel/vendor)"
  if [ -r "$1" ]; then limited cat "$1" | sed -n '1,180p;180q'; else printf 'NA\n'; fi
}
own_profiles() {
  heading 'Own experimental profiles (pause/disable markers are not activity proof)'
  for id in chatgpt-fluidez-memoria chatgpt-cpu-respuesta; do
    dir=/data/adb/$id
    printf '%s:\n' "$id"
    if [ -d "$dir" ] && [ ! -L "$dir" ]; then
      if [ -f "$dir/paused" ] && [ ! -L "$dir/paused" ]; then printf 'paused: yes\n'; else printf 'paused: no marker\n'; fi
      if [ -f "$dir/history.log" ] && [ ! -L "$dir/history.log" ]; then limited tail -n 40 "$dir/history.log"; fi
    else printf 'NA\n'; fi
  done
  for id in chatgpt_cpu_respuesta chatgpt_fluidez_memoria; do
    if [ -f "/data/adb/modules/$id/disable" ]; then printf '%s: Manager disable marker present\n' "$id"; fi
  done
}
clock_sample() {
  # uptime includes suspend. timer_list's header uses ktime_get() (monotonic).
  # Only the first eight lines are read; timer addresses/owners are not exported.
  clock_uptime=$(limited cat /proc/uptime | sed -n '1s/ .*//p')
  clock_mono=$(limited sh -c 'sed -n "1,8p;8q" /proc/timer_list' 2>/dev/null |
    sed -n 's/^now at \([0-9][0-9]*\) nsecs$/\1/p' | sed -n '1p')
  printf '%s\n' "$BOOT_ID" > "$STATE/$1.boot" || return 1
  printf '%s\n' "$clock_uptime" > "$STATE/$1.uptime" || return 1
  printf '%s\n' "$clock_mono" > "$STATE/$1.mono" || return 1
  printf 'Clock sample UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
  printf 'boottime_seconds (/proc/uptime; includes suspend): %s\n' "${clock_uptime:-NA}"
  printf 'monotonic_nanoseconds (timer_list; excludes suspend): %s\n' "${clock_mono:-NA}"
}
capture() {
  heading "$1 snapshot"
  clock_sample "$1" || return 1
  uname -a
  for prop in ro.product.device ro.build.display.id ro.lineage.version; do printf '%s: ' "$prop"; limited getprop "$prop"; done
  heading 'Battery raw units: temp usually tenths C, current usually microamps; sign is driver-specific'
  for field in status capacity temp current_now current_avg voltage_now charge_counter; do value "/sys/class/power_supply/battery/$field"; done
  heading 'CPU, memory and pressure (cumulative counters; CPU process percentages may be lifetime averages)'
  value /proc/loadavg
  limited cat /proc/stat | sed -n '/^cpu/p; /^procs_/p'
  limited cat /proc/meminfo | sed -n '/^MemAvailable:/p; /^SwapTotal:/p; /^SwapFree:/p; /^Cma/p'
  limited cat /proc/vmstat | grep -E '^(pgscan|pgsteal|allocstall|pswpin|pswpout|workingset_refault|oom_kill|kswapd_).* ' | sed -n '1,70p;70q'
  for field in cpu memory io; do value "/proc/pressure/$field"; done
  value /proc/sys/vm/watermark_scale_factor
  value /sys/kernel/mm/lru_gen/enabled
  value /sys/block/zram0/disksize
  value /sys/block/zram0/mm_stat
  heading 'Process names and CPU time only; no arguments or task stacks'
  limited ps -A -o PID,STAT,PCPU,TIME,NAME | sed -n '1,400p;400q'
  heading 'CPU and GPU controls (read only)'
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    for field in scaling_governor scaling_min_freq scaling_max_freq scaling_cur_freq; do value "$policy/$field"; done
    value "$policy/walt/up_rate_limit_us"
  done
  value /sys/devices/system/cpu/cpufreq/walt/up_rate_limit_us
  for field in gpuclk idle_timer force_clk_on force_bus_on force_rail_on; do value "/sys/class/kgsl/kgsl-3d0/$field"; done
  value /sys/class/kgsl/kgsl-3d0/devfreq/governor
  heading 'CPU idle states (not proof of system suspend; vendor units)'
  for idle in /sys/devices/system/cpu/cpu0/cpuidle/state* /sys/devices/system/cpu/cpu4/cpuidle/state*; do
    [ -d "$idle" ] || continue
    for field in name time usage disable; do value "$idle/$field"; done
  done
  value /sys/power/state
  value /sys/power/mem_sleep
  value /sys/power/wakeup_count
  for field in success fail failed_freeze failed_prepare failed_suspend failed_suspend_late failed_suspend_noirq failed_resume_noirq failed_resume_early failed_resume last_failed_dev last_failed_errno last_failed_step; do
    value "/sys/power/suspend_stats/$field"
  done
  table /sys/kernel/debug/suspend_stats
  table /sys/kernel/debug/wakeup_sources
  table /sys/kernel/wakeup_reasons/last_resume_reason
  table /sys/kernel/wakeup_reasons/last_suspend_time
  heading 'Android power state and suspend blockers (selected fields only)'
  limited dumpsys power | sed -n -E '
    /mWakefulness=|mIsPowered=|mPlugType=|mWakeLockSummary=|mUserActivitySummary=|mHalAutoSuspendModeEnabled=|mHalInteractiveModeEnabled=|mHoldingWakeLockSuspendBlocker=|mHoldingDisplaySuspendBlocker=|mLastWakeTime=|mLastSleepTime=|mLastWakeReason=|mLastSleepReason=/p
    /^Wake Locks:/,/^$/p
    /^Suspend Blockers:/,/^$/p
    /^Display Power: state=/p
  ' | sed -n '1,200p;200q'
  heading 'Android suspend control (counters and wake lock names; no reset)'
  limited dumpsys suspend_control_internal | sed -n '1,220p;220q'
  heading 'Device idle state (Doze is distinct from kernel suspend)'
  limited dumpsys deviceidle | grep -E 'm(State|LightState|ScreenOn|Charging|NetworkConnected|ForceIdle)=' | sed -n '1,30p;30q'
  heading 'Screen projection owner (Android 13 format; package/UID/type only)'
  projection_selected=$(limited dumpsys media_projection | grep -E '^(MEDIA PROJECTION MANAGER \(dumpsys media_projection\)|Media Projection: *|null|\([A-Za-z0-9_.]+, uid=[0-9]+\): [A-Z_0-9]+)$' | sed -n '1,10p;10q')
  if [ -n "$projection_selected" ]; then printf '%s\n' "$projection_selected"; else printf 'NA: service unavailable or unrecognized format; no absence inferred.\n'; fi
  heading 'Wireless display flags only (do not include display names or network addresses)'
  limited dumpsys display | grep -E '^[[:space:]]*m(WifiDisplayOn|WifiDisplayEnabled|WifiDisplayConnected|RemoteDisplayConnected)=(true|false)$' | sed -n '1,12p;12q'
  heading 'Battery accounting totals (may reset on charge/reboot; compare matching accounting periods only)'
  limited dumpsys batterystats --charged | grep -E '^[[:space:]]*(Start clock time:|System starts:|Time on battery:|Time on battery screen off:|Total run time:|Screen on:|Screen off:|Interactive:|Device light doze:|Device full doze:)' | sed -n '1,35p;35q'
  heading 'Selected suspend/freeze/thermal kernel messages since boot (may predate interval)'
  limited dmesg | grep -iE 'PM: suspend|suspend entry|suspend exit|suspend.*fail|suspend.*abort|active wakeup|wakeup.*reason|freezing.*fail|tasks refusing|thermal.*(critical|shutdown)|watchdog.*(lockup|bark)' | tail -n 100
  own_profiles
  printf 'SNAPSHOT COMPLETE: %s\n' "$1"
}
interval_summary() {
  heading 'Interval summary (includes time operating the collector; screen-off duration not assumed)'
  start_boot=$(cat "$STATE/START.boot") || return 1
  end_boot=$(cat "$STATE/END.boot") || return 1
  if [ "$start_boot" != "$end_boot" ]; then
    printf 'BOOT CHANGED: cumulative counters and clocks must not be subtracted.\n'
    return
  fi
  awk 'FNR==1 { v[++n]=$1 }
    END {
      if(n!=4 || v[1]!~/^[0-9]+([.][0-9]+)?$/ || v[2]!~/^[0-9]+([.][0-9]+)?$/) { print "Interval clocks unavailable; use raw counters."; exit }
      b=v[2]-v[1]; if(b<=0) { print "Invalid/zero interval; no ratio computed."; exit }
      printf "Elapsed boottime (includes suspend): %.2f seconds\n",b
      if(v[3]!~/^[0-9]+$/ || v[4]!~/^[0-9]+$/) { print "Monotonic clock unavailable; suspend duration not computed."; exit }
      m=(v[4]-v[3])/1000000000; s=b-m
      if(m<0 || s < -0.1 || s>b+0.1) { print "Inconsistent clock samples; suspend ratio not computed."; exit }
      if(s<0)s=0; if(s>b)s=b
      printf "Approximate system-suspended time: %.2f seconds (%.1f%% of interval)\n",s,100*s/b
      print "Clock sampling is sequential; estimate, not a hardware low-power residency measurement."
    }' "$STATE/START.uptime" "$STATE/END.uptime" "$STATE/START.mono" "$STATE/END.mono"
}
unlock() { rm -f "$STATE/lock/pid" "$STATE/lock/boot"; rmdir "$STATE/lock" 2>/dev/null; }

[ "$(id -u)" = 0 ] || fail 'KernelSU root is required.'
MODE=${1:-auto}
case "$MODE" in start|finish|auto) :;; *) fail 'Use start, finish or auto.';; esac
command -v timeout >/dev/null 2>&1 || fail 'A bounded timeout command is required.'
[ ! -L "$STATE" ] || fail 'Private state is a symlink; no changes made.'
if [ ! -d "$STATE" ]; then mkdir "$STATE" || fail 'Cannot create private state.'; fi
[ "$(stat -c %u "$STATE" 2>/dev/null)" = 0 ] || fail 'Private state is not root owned.'
chmod 700 "$STATE" || fail 'Cannot secure private state.'
for file in pending.txt staging.txt START.boot START.uptime START.mono END.boot END.uptime END.mono; do
  [ ! -L "$STATE/$file" ] || fail 'Private state contains a symlink; no data read.'
  if [ -e "$STATE/$file" ]; then [ -f "$STATE/$file" ] || fail 'Invalid private state file.'; fi
done
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
[ -n "$BOOT_ID" ] || fail 'Cannot identify the current boot.'
[ ! -L "$STATE/lock" ] || fail 'Invalid lock.'
if ! mkdir "$STATE/lock" 2>/dev/null; then
  old_pid=$(cat "$STATE/lock/pid" 2>/dev/null)
  old_boot=$(cat "$STATE/lock/boot" 2>/dev/null)
  case "$old_pid" in ''|*[!0-9]*) fail 'Incomplete diagnostic lock; wait for the current capture.';; esac
  if [ "$old_boot" = "$BOOT_ID" ] && kill -0 "$old_pid" 2>/dev/null; then fail 'A snapshot is already running.'; fi
  unlock
  mkdir "$STATE/lock" 2>/dev/null || fail 'Cannot acquire diagnostic lock.'
fi
trap unlock 0
trap 'exit 130' 1 2 15
printf '%s\n' "$$" > "$STATE/lock/pid"
printf '%s\n' "$BOOT_ID" > "$STATE/lock/boot"
if [ "$MODE" = auto ]; then if [ -f "$STATE/pending.txt" ]; then MODE=finish; else MODE=start; fi; fi
if [ "$MODE" = start ]; then
  [ ! -f "$STATE/pending.txt" ] || fail 'A baseline already exists. Use finish or press Action again.'
  capture START > "$STATE/staging.txt" 2>&1 || fail 'Baseline capture failed.'
  mv "$STATE/staging.txt" "$STATE/pending.txt" || fail 'Cannot save baseline.'
  printf 'START SAVED. The collector has finished; no background process remains.\n'
  printf 'Unplug USB/charger, turn the screen off and leave the phone untouched for about 10 minutes.\n'
  printf 'Then unlock it and press Action again, or run the same script with finish.\n'
  exit 0
fi
[ -f "$STATE/pending.txt" ] || fail 'No baseline. Use start or press Action first.'
for file in START.boot START.uptime START.mono; do [ -f "$STATE/$file" ] || fail 'Baseline metadata incomplete; preserve private state for diagnosis.'; done
[ -d "$DOWNLOADS" ] && [ -w "$DOWNLOADS" ] || fail 'Unlock the phone: Download storage unavailable. Baseline preserved.'
OUTPUT="$DOWNLOADS/ChatGPT-Reposo-$(date -u '+%Y%m%d-%H%M%S')-$$.txt"
(set -C; : > "$OUTPUT") 2>/dev/null || fail 'Output already exists or cannot be created. Baseline preserved.'
{
  heading 'ChatGPT Reposo diagnostic v1' &&
  printf 'Two snapshots; no collector process, alarms or wake locks between them. No settings changed.\n' &&
  cat "$STATE/pending.txt" &&
  capture END &&
  interval_summary &&
  printf 'No reset, forced suspend, app stopping, tuning or automatic upload was performed.\n' &&
  heading 'TEST FINISHED'
} >> "$OUTPUT" 2>&1 || fail 'Report incomplete. Baseline preserved.'
rm -f "$STATE/pending.txt"
printf 'TEST FINISHED. Share this file:\n%s\n' "$OUTPUT"
