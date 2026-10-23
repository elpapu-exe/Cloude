#!/system/bin/sh
# Read-only, one-shot SecureElement/TikTok diagnostic. No app/service changes or upload.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077

fail() { printf '%s\n' "$*" >&2; exit 1; }
heading() { printf '\n=== %s ===\n' "$*"; }
read_value() {
  if [ -r "$1" ]; then cat "$1" 2>/dev/null || printf 'NA\n'; else printf 'NA\n'; fi
}
bounded() {
  timeout 6 "$@" 2>&1
  result=$?
  [ "$result" -eq 0 ] || printf '[command %s exit status: %s]\n' "$1" "$result"
  return "$result"
}
trace_search_bounded() {
  remaining=$((20 - ($(date +%s) - TRACE_SEARCH_START)))
  [ "$remaining" -gt 0 ] || return 124
  limit=6
  [ "$remaining" -ge "$limit" ] || limit=$remaining
  timeout "$limit" "$@" 2>&1
  result=$?
  [ "$result" -eq 0 ] || printf '[command %s exit status: %s]\n' "$1" "$result"
  return "$result"
}
cleanup() { rm -f "$WORK/lastanr" "$WORK/capture"; rmdir "$WORK" 2>/dev/null; }

[ "$(id -u)" = 0 ] || fail 'Run this script with KernelSU root.'
command -v timeout >/dev/null 2>&1 || fail 'Android timeout command is required.'
[ -d /sdcard/Download ] && [ -w /sdcard/Download ] || fail 'Unlock the phone: Download storage is unavailable.'
WORK=$(mktemp -d /data/local/tmp/chatgpt-se.XXXXXX) || fail 'Cannot create temporary directory.'
trap cleanup 0
trap 'exit 130' 1 2 15
OUTPUT="/sdcard/Download/ChatGPTKernel-SE-$(date -u '+%Y%m%d-%H%M%S')-$$.txt"

collect() {
  heading 'ChatGPT Kernel SecureElement/TikTok diagnostic v2 (read only)'
  printf 'UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
  uname -r
  for property in ro.product.device ro.build.display.id ro.lineage.version; do
    printf '%s: ' "$property"; getprop "$property"
  done

  heading 'Last ANR summary (only if the primary process is SecureElement or TikTok)'
  bounded dumpsys activity lastanr > "$WORK/lastanr"
  status=$?
  printf 'dumpsys exit status: %s\n' "$status"
  primary_line=$(sed -n '1,25p' "$WORK/lastanr" | sed -n -E '/^[[:space:]]*(ANR in |Process: )/{p;q;}')
  if printf '%s\n' "$primary_line" | grep -qE '^[[:space:]]*(ANR in |Process: )com\.(android\.se|zhiliaoapp\.musically|ss\.android\.ugc\.trill)([[:space:](]|$)'; then
    sed -n -E '/^[[:space:]]*(ANR time:|ANR in |Process:|PID:|UID:|Reason:|ErrorId:|Frozen:|Load:)/p' "$WORK/lastanr" | sed -n '1,25p'
  else
    printf 'No primary SecureElement/TikTok ANR summary; other-app contents omitted.\n'
  fi

  heading 'SecureElement process only in the three newest ANR traces'
  count=0; found=0
  for trace in $(ls -1t /data/anr/anr_* 2>/dev/null); do
    count=$((count + 1)); [ "$count" -le 3 ] || break
    bounded grep -qE '^Cmd line: com\.android\.se$' "$trace" > "$WORK/capture"
    status=$?
    if [ "$status" -eq 0 ]; then
      found=$((found + 1))
      printf '\nTrace: %s\nmtime epoch: ' "$trace"; stat -c %Y "$trace" 2>/dev/null
      printf 'SE may be a secondary process; presence alone does not identify the ANR victim.\n'
      # Stop at the next process even if an interrupted trace lacks its end marker.
      bounded sed -n -E '/^Cmd line: com\.android\.se$/,/^----- (end|pid )/{
        /^----- pid /q
        p
        /^----- end/q
      }' "$trace" | sed -n '1,260p;260q'
    elif [ "$status" -gt 1 ]; then
      cat "$WORK/capture"
    fi
  done
  [ "$found" -gt 0 ] || printf 'No readable SecureElement process section found in the three newest traces.\n'

  heading 'One TikTok process section from the 32 newest ANR traces (max 260 lines)'
  count=0; primary_trace=; secondary_trace=
  TRACE_SEARCH_START=$(date +%s)
  for trace in $(ls -1t /data/anr/anr_* 2>/dev/null); do
    count=$((count + 1)); [ "$count" -le 32 ] || break
    [ $(($(date +%s) - TRACE_SEARCH_START)) -lt 20 ] || break
    first_command=$(trace_search_bounded sed -n '/^Cmd line: /{p;q;}' "$trace")
    case "$first_command" in
      'Cmd line: com.zhiliaoapp.musically'|'Cmd line: com.ss.android.ugc.trill')
        primary_trace=$trace; break;;
    esac
    if [ -z "$secondary_trace" ]; then
      if trace_search_bounded grep -qE '^Cmd line: (com\.zhiliaoapp\.musically|com\.ss\.android\.ugc\.trill)$' "$trace" > "$WORK/capture"; then
        secondary_trace=$trace
      fi
    fi
  done
  if [ -z "$primary_trace" ] && [ $(($(date +%s) - TRACE_SEARCH_START)) -ge 20 ]; then
    printf 'TikTok trace search stopped: 20-second time budget exhausted.\n'
  fi
  if [ -n "$primary_trace" ]; then
    selected_trace=$primary_trace
    printf 'Trace role: primary (first Cmd line is TikTok).\n'
  else
    selected_trace=$secondary_trace
    [ -z "$selected_trace" ] || printf 'Trace role: secondary; presence alone does not identify the ANR victim.\n'
  fi
  if [ -n "$selected_trace" ]; then
    printf 'Trace: %s\nmtime epoch: ' "$selected_trace"; stat -c %Y "$selected_trace" 2>/dev/null
    # Stop after one matching process, including when a trace lacks an end marker.
    bounded sed -n -E '/^Cmd line: (com\.zhiliaoapp\.musically|com\.ss\.android\.ugc\.trill)$/,/^----- (end|pid )/{
      /^----- pid /q
      p
      /^----- end/q
    }' "$selected_trace" | sed -n '1,260p;260q'
  else
    printf 'No readable TikTok process section found in the 32 newest traces.\n'
  fi

  heading 'Current battery and CPU frequency limits (read only; frequency in kHz)'
  printf 'battery temperature (tenths C): '; read_value /sys/class/power_supply/battery/temp
  printf 'battery status: '; read_value /sys/class/power_supply/battery/status
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    printf '%s:\n' "$policy"
    for field in scaling_min_freq scaling_max_freq cpuinfo_max_freq; do
      printf '  %s: ' "$field"; read_value "$policy/$field"
    done
  done
  heading 'Current cooling devices (first 32; read only)'
  count=0
  for cooling in /sys/class/thermal/cooling_device*; do
    [ -d "$cooling" ] || continue
    count=$((count + 1)); [ "$count" -le 32 ] || break
    printf '%s:\n' "$cooling"
    for field in type cur_state max_state; do
      printf '  %s: ' "$field"; read_value "$cooling/$field"
    done
  done
  heading 'Current thermal service snapshot (max 100 lines)'
  bounded dumpsys thermalservice > "$WORK/capture"
  printf 'thermalservice exit status: %s\n' "$?"
  sed -n '1,100p;100q' "$WORK/capture"

  heading 'Recent SecureElement ANR/kill events only (max 50)'
  bounded logcat -d -t 1000 -b events -v threadtime am_anr:I am_kill:I '*:S' > "$WORK/capture"
  printf 'logcat exit status: %s\n' "$?"
  if grep -E 'am_(anr|kill).*[, ]com\.android\.se,' "$WORK/capture" > /dev/null; then
    grep -E 'am_(anr|kill).*[, ]com\.android\.se,' "$WORK/capture" | tail -n 50
  else
    printf 'No matching events in this bounded log snapshot.\n'
  fi

  heading 'SecureElement Binder services'
  bounded service list > "$WORK/capture"
  printf 'service list exit status: %s\n' "$?"
  grep -iE 'secure.?element|omapi' "$WORK/capture" || printf 'No matching Binder service.\n'
  heading 'SecureElement HAL registrations'
  bounded lshal > "$WORK/capture"
  printf 'lshal exit status: %s\n' "$?"
  grep -iE 'secure.?element|omapi' "$WORK/capture" || printf 'No matching HAL in captured output.\n'
  heading 'SecureElement declared Android features'
  bounded pm list features > "$WORK/capture"
  printf 'pm exit status: %s\n' "$?"
  grep -iE 'secure.?element|omapi' "$WORK/capture" || printf 'No matching Android feature.\n'

  heading 'FINISHED'
  printf 'No settings or services were changed; no files were uploaded.\n'
}

collect > "$OUTPUT" 2>&1 || fail "Diagnostic incomplete; partial report: $OUTPUT"
printf 'Done. Share this one text file:\n%s\n' "$OUTPUT"
