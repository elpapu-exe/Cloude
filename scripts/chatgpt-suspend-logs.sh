#!/system/bin/sh
# ChatGPT Reposo diagnostic v3: two snapshots, no process between them.
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
process_activity() {
  heading 'Userspace and selected kernel CPU times (names only; no arguments; percentages may be lifetime averages)'
  # Kernel threads precede most apps by PID. Do not let a prefix cap hide the apps.
  limited ps -A -o PID,STAT,PCPU,TIME,NAME | awk '
    NR==1 && $1=="PID" {print; next}
    $1 !~ /^[0-9]+$/ {next}
    $5 ~ /^\[/ {
      if ($5 ~ /^\[(kswapd|kcompactd|qrtr|cnss)/ && kernels++<12) print
      next
    }
    users++ < 300 {print}
    END {if (!users) print "NA: userspace process rows unavailable"}
  '
}
network_activity() {
  heading 'Network configuration flags (preferences, not proof of the active default transport)'
  for key in wifi_on mobile_data airplane_mode_on; do
    printf '%s: ' "$key"
    flag=$(limited settings get global "$key")
    case "$flag" in 0|1|2|3) printf '%s\n' "$flag";; *) printf 'NA\n';; esac
  done
  heading 'Wireless/mobile interface byte counters (no IP, SSID or hardware addresses)'
  limited cat /proc/net/dev | awk '
    {name=$1; sub(/:$/,"",name)}
    name ~ /^(wlan[0-9]+|rmnet[a-zA-Z0-9_]*|ccmni[0-9]+|pdp[0-9]+)$/ && $2 ~ /^[0-9]+$/ && $10 ~ /^[0-9]+$/ {
      print name,"rx_bytes",$2,"tx_bytes",$10; rows++
    }
    END {if (!rows) print "NA: matching interface counters unavailable"}
  '
  heading 'Relevant loaded module names, sizes and references (not proof of exact module sources)'
  limited cat /proc/modules | awk '
    $1 ~ /^(qrtr|icnss|cnss|qmi|glink|wlan|walt|msm_kgsl)[A-Za-z0-9_]*$/ && $2 ~ /^[0-9]+$/ && $3 ~ /^-?[0-9]+$/ {print $1,$2,$3; rows++}
    END {if (!rows) print "NA: matching module rows unavailable"}
  '
}
bt_text() {
  printf '%s: ' "$1"
  if [ -r "$1" ]; then
    limited cat "$1" | tr '\000' '\n' | sed -n '1,6p;6q'
  else printf 'NA\n'; fi
}
bt_link() {
  printf '%s: ' "$1"
  if [ -e "$1" ]; then
    bt_link_target=$(limited readlink -f "$1")
    if [ "$?" -eq 0 ] && [ -n "$bt_link_target" ]; then printf '%s\n' "$bt_link_target"; else printf 'NA\n'; fi
  else printf 'NA\n'; fi
}
bluetooth_manager_summary() {
  heading 'Bluetooth manager state and supported GATT scan rows (peer names/addresses omitted)'
  # Android 13/Lineage 20 format. Raw Bluetooth dump is never saved or exported.
  limited dumpsys bluetooth_manager | awk '
    NR>20000 {print "NA: Bluetooth manager reader truncated"; exit}
    /^Bluetooth Status$/ {status=1; next}
    status && /^$/ {status=0}
    status && /^  enabled: (true|false)$/ {print "adapter_enabled",$2; states++; next}
    status && /^  state: [A-Z_]+$/ {print "adapter_state",$2; states++; next}
    /^[[:space:]]*GATT Scanner Map[[:space:]]*$/ {scan=1; section=1; app=""; next}
    scan && /^[[:space:]]*GATT .* Map[[:space:]]*$/ {scan=0; app=""; next}
    scan && /^[^[:space:]]/ {scan=0; app=""; next}
    scan && /^  [^[:space:]].*:[[:space:]]*$/ && $0 !~ /^  (Last [0-9]+ scans|Ongoing scans)[[:space:]]*:/ {scan=0; app=""; next}
    scan && /^  [^[:space:]]+([[:space:]]+\(Registered\))?$/ {
      app=""; name=$0; sub(/^  /,"",name); sub(/ \(Registered\)$/, "",name)
      if(name ~ /^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$/ && apps++<128) {
        app=name; print "BLE scanner package",app
      } else if(name !~ /^android[.]uid[.][A-Za-z_]+:[0-9]+$/) {
        scan=0
      }
      next
    }
    scan && app!="" && /^  LE scans \(started\/stopped\)[[:space:]]*:/ && $NF ~ /^[0-9]+$/ && $(NF-2) ~ /^[0-9]+$/ {
      print "BLE scan counts",app,"started",$(NF-2),"stopped",$NF; next
    }
    scan && app!="" && /^  Scan time in ms \(active\/suspend\/total\)[[:space:]]*:/ && $NF ~ /^[0-9]+$/ && $(NF-2) ~ /^[0-9]+$/ && $(NF-4) ~ /^[0-9]+$/ {
      print "BLE scan time_ms",app,"active",$(NF-4),"suspended",$(NF-2),"total",$NF; next
    }
    scan && app!="" && /^  Ongoing scans[[:space:]]*:$/ {print "BLE ongoing scan section observed",app; next}
    END {
      if(!states) print "NA: Bluetooth adapter state format unavailable"
      if(!section || !apps) print "NA: supported BLE scanner attribution unavailable; no absence inferred"
      print "Scan rows may include historical registration/counters; they do not prove the source of a UART vote."
    }
  '
}
bluetooth_runtime() {
  heading 'Bluetooth flags and fixed property allowlist (read only; missing is not a default value)'
  for bt_key in bluetooth_on ble_scan_always_enabled; do
    bt_flag=$(limited settings get global "$bt_key")
    printf '%s: ' "$bt_key"
    case "$bt_flag" in 0|1|2|3) printf '%s\n' "$bt_flag";; *) printf 'NA\n';; esac
  done
  # Never dump all properties: Bluetooth name/address keys can identify peers.
  for bt_property in ro.vendor.build.fingerprint ro.vendor.build.version.release \
    ro.vendor.build.security_patch ro.vendor.bluetooth.soc qcom.bluetooth.soc \
    vendor.qcom.bluetooth.soc persist.vendor.qcom.bluetooth.soc \
    ro.bluetooth.library_name persist.service.bdroid.sibs \
    persist.vendor.service.bdroid.sibs persist.bluetooth.btsnooplogmode \
    persist.vendor.service.bdroid.soclog persist.vendor.qcom.bluetooth.soclog \
    persist.vendor.qcom.bluetooth.disable_ibs persist.vendor.bluetooth.disable_ibs \
    init.svc.vendor.qti.bluetooth-1-0 init.svc.vendor.qti.bluetooth-1-1 \
    init.svc.vendor.bluetooth-1-0; do
    bt_prop_value=$(limited getprop "$bt_property")
    printf '%s: %s\n' "$bt_property" "${bt_prop_value:-NA}"
  done
  heading 'UART alias and TTY mappings (hardware paths only; no UART device is opened)'
  for bt_index in 0 1 2 3; do bt_text "/sys/firmware/devicetree/base/aliases/hsuart$bt_index"; done
  bt_tty_count=0
  for bt_tty in /sys/class/tty/ttyHS*; do
    [ -d "$bt_tty" ] || continue
    bt_tty_count=$((bt_tty_count+1)); [ "$bt_tty_count" -le 8 ] || break
    bt_link "$bt_tty/device"
    bt_link "$bt_tty/device/of_node"
    bt_link "$bt_tty/device/driver"
  done
  [ "$bt_tty_count" -gt 0 ] || printf 'NA: ttyHS sysfs mappings unavailable\n'
  heading 'Retained UART runtime power, firmware node and loaded driver (read only)'
  bt_uart_count=0
  for bt_uart in /sys/bus/platform/devices/*4a8c000*; do
    [ -d "$bt_uart" ] || continue
    bt_uart_count=$((bt_uart_count+1)); [ "$bt_uart_count" -le 4 ] || break
    printf 'UART path: %s\n' "$bt_uart"
    bt_link "$bt_uart/driver"
    bt_link "$bt_uart/driver/module"
    for bt_field in runtime_status control runtime_active_time runtime_suspended_time \
      autosuspend_delay_ms runtime_usage wakeup wakeup_active wakeup_active_count wakeup_total_time_ms; do
      value "$bt_uart/power/$bt_field"
    done
    bt_text "$bt_uart/of_node/compatible"
    printf 'DT qcom,auto-suspend-disable: '
    if [ -d "$bt_uart/of_node" ] && [ -r "$bt_uart/of_node/compatible" ]; then
      if [ -e "$bt_uart/of_node/qcom,auto-suspend-disable" ]; then printf 'present\n'; else printf 'absent\n'; fi
    else printf 'NA: firmware node unavailable\n'; fi
    bt_module=
    if [ -d "$bt_uart/driver/module" ]; then bt_module=$(limited readlink -f "$bt_uart/driver/module"); fi
    case "$bt_module" in /sys/module/*) :;; *) bt_module=;; esac
    if [ -n "$bt_module" ]; then
      for bt_field in version srcversion taint; do value "$bt_module/$bt_field"; done
      bt_module_name=${bt_module##*/}
      case "$bt_module_name" in ''|*[!A-Za-z0-9_]*) printf 'NA: module filename unlisted\n';;
        *)
          bt_binary_count=0
          for bt_modules_dir in /vendor_dlkm/lib/modules /vendor/lib/modules /system_dlkm/lib/modules /system/lib/modules; do
            bt_binary="$bt_modules_dir/$bt_module_name.ko"
            [ -r "$bt_binary" ] && [ -f "$bt_binary" ] || continue
            bt_binary_count=$((bt_binary_count+1))
            printf 'Candidate module SHA256 (not source provenance proof): '
            limited sha256sum "$bt_binary"
          done
          [ "$bt_binary_count" -gt 0 ] || printf 'NA: module binary not exposed at checked paths\n';;
      esac
    fi
  done
  [ "$bt_uart_count" -gt 0 ] || printf 'NA: retained UART node unavailable\n'
  heading 'TTY descriptors seen in named Bluetooth candidates (bounded; no match does not prove port closed)'
  # Read symlink targets only, never the device or fd contents, cmdline, sockets,
  # peer addresses, RX/TX buffers, or Bluetooth packet logs.
  limited sh -c '
    owner_ps_output=$(ps -A -o PID,NAME 2>/dev/null)
    if [ "$?" -ne 0 ] || [ -z "$owner_ps_output" ]; then
      printf "NA: candidate process reader unavailable\n"
      exit 1
    fi
    printf "%s\n" "$owner_ps_output" | {
    while read -r owner_pid owner_name rest; do
      case "$owner_pid" in ""|*[!0-9]*) continue;; esac
      case "$owner_name" in *bluetooth*|*wcnss_filter*|*hciattach*|*bt_vendor*) :;; *) continue;; esac
      case "$owner_name" in *[!A-Za-z0-9_.:@+-]*) continue;; esac
      candidate_count=$((candidate_count+1)); [ "$candidate_count" -le 8 ] || break
      seen=0; fd_count=0
      for owner_fd in /proc/"$owner_pid"/fd/*; do
        [ -L "$owner_fd" ] || continue
        fd_count=$((fd_count+1)); [ "$fd_count" -le 512 ] || break
        owner_target=$(readlink "$owner_fd" 2>/dev/null)
        case "$owner_target" in /dev/ttyHS[0-9]|/dev/ttyHS[0-9][0-9])
          printf "TTY owner candidate: %s %s %s\n" "$owner_pid" "$owner_name" "$owner_target"
          seen=$((seen+1));;
        esac
      done
      [ "$seen" -gt 0 ] || printf "No TTY descriptor observed: %s %s (absent, closed, or access denied)\n" "$owner_pid" "$owner_name"
    done
    [ "${candidate_count:-0}" -gt 0 ] || printf "NA: no named Bluetooth candidates observed; owner unknown\n"
    }
  '
  printf 'TTY candidate probe exit status: %s (nonzero may mean incomplete scan)\n' "$?"
  bluetooth_manager_summary
}
battery_accounting() {
  heading 'Battery accounting and UID totals (same accounting period required; no alarm tags or history)'
  # Use the human --charged reader. --checkin may consume a completed checkin
  # file on Android 13; -c includes history. Neither is used here.
  limited dumpsys batterystats --charged | awk '
    function valid_duration(s, test) {
      test=s
      gsub(/actual background partial|actual partial|blamed partial|full|window|draw|realtime/,"",test)
      gsub(/[0-9dhms,. ]/,"",test)
      return test=="" && s ~ /[0-9]/
    }
    NR>25000 {print "NA: battery accounting reader truncated"; exit}
    /^[[:space:]]*(Start clock time:|System starts:|Time on battery:|Time on battery screen off:|Total run time:|Screen on:|Screen off:|Interactive:|Device light doze:|Device full doze:)/ {print; next}
    /^  [^[:space:]].*:$/ {
      uid=""; pkg=""
      if ($0 ~ /^  ([0-9]+|u[0-9]+[asi][0-9]+):$/) {
        uid=$1; sub(/:$/,"",uid); uidrows++
      }
      next
    }
    uid!="" && /^    TOTAL wake: / {
      text=$0; sub(/^    TOTAL wake: /,"",text)
      if (length(text)<350 && valid_duration(text) && wakes++<300) print "uid_wakelock",uid,text
      next
    }
    /^    Apk / {
      pkg=""
      if (uid!="" && $0 ~ /^    Apk [A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+:$/) {
        pkg=$2; sub(/:$/,"",pkg)
        if (packages++<400) print "uid_package",uid,pkg
      }
      next
    }
    uid!="" && pkg!="" && /^      Wakeup alarm / && $NF=="times" && $(NF-1) ~ /^[0-9]+$/ {
      key=uid SUBSEP pkg
      if (!(key in alarms) && alarmkeys++>=400) next
      alarms[key]+=$(NF-1); next
    }
    END {
      for (key in alarms) {split(key,p,SUBSEP); printf "uid_wakeup_alarm_count %s %s %.0f\n",p[1],p[2],alarms[key]}
      if (!uidrows) print "NA: UID accounting format unavailable; no zero usage inferred"
      print "Selected cumulative UID rows only; overlapping UID wakelocks must not be added as elapsed time."
    }
  '
}
kernel_suspend_details() {
  heading 'Freezer outcomes and wake-abort details (separate bounded rings; since boot, may predate interval)'
  limited dmesg | awk '
    /Freezing of tasks (aborted|failed)|tasks refusing to freeze/ {outcomes[nout%60]=$0; nout++}
    /Last active Wakeup Source|Pending Wakeup Sources|Callback failed on/ {events[nevent%80]=$0; nevent++}
    END {
      print "Freezer outcome summaries (last 60):"
      for(i=(nout>60?nout-60:0);i<nout;i++) print outcomes[i%60]
      if(!nout) print "NA: no freezer outcome summaries available in retained messages"
      print "Wake-abort detail messages (last 80):"
      for(i=(nevent>80?nevent-80:0);i<nevent;i++) print events[i%80]
      if(!nevent) print "NA: no wake-abort details available in retained messages"
    }
  '
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
  process_activity
  network_activity
  bluetooth_runtime
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
  battery_accounting
  kernel_suspend_details
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
  heading 'ChatGPT Reposo diagnostic v3' &&
  printf 'Two snapshots; no collector process, alarms or wake locks between them. No settings changed.\n' &&
  cat "$STATE/pending.txt" &&
  capture END &&
  interval_summary &&
  printf 'No reset, forced suspend, app stopping, tuning or automatic upload was performed.\n' &&
  heading 'TEST FINISHED'
} >> "$OUTPUT" 2>&1 || fail 'Report incomplete. Baseline preserved.'
rm -f "$STATE/pending.txt"
printf 'TEST FINISHED. Share this file:\n%s\n' "$OUTPUT"
