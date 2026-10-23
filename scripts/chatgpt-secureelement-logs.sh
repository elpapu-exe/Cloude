#!/system/bin/sh
# Read-only, one-shot SecureElement diagnostic. No app/service changes or upload.
PATH=/system/bin:/system/xbin:/vendor/bin:/product/bin
export PATH
umask 077

fail() { printf '%s\n' "$*" >&2; exit 1; }
heading() { printf '\n=== %s ===\n' "$*"; }
bounded() {
  timeout 6 "$@" 2>&1
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
  heading 'ChatGPT Kernel SecureElement diagnostic v1 (read only)'
  printf 'UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
  uname -r
  for property in ro.product.device ro.build.display.id ro.lineage.version; do
    printf '%s: ' "$property"; getprop "$property"
  done

  heading 'Last ANR summary (only if the primary process is com.android.se)'
  bounded dumpsys activity lastanr > "$WORK/lastanr"
  status=$?
  printf 'dumpsys exit status: %s\n' "$status"
  if sed -n '1,25p' "$WORK/lastanr" | grep -qE '^[[:space:]]*(ANR in |Process: )com\.android\.se([[:space:](]|$)'; then
    sed -n -E '/^[[:space:]]*(ANR time:|ANR in |Process:|PID:|UID:|Reason:|ErrorId:|Frozen:|Load:)/p' "$WORK/lastanr" | sed -n '1,25p'
  else
    printf 'No primary SecureElement ANR summary; other-app contents omitted.\n'
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
      # ANR pid markers are adjacent to Cmd line; extract only the matched process.
      bounded sed -n -E '/^Cmd line: com\.android\.se$/,/^----- end/p' "$trace" | sed -n '1,260p'
    elif [ "$status" -gt 1 ]; then
      cat "$WORK/capture"
    fi
  done
  [ "$found" -gt 0 ] || printf 'No readable SecureElement process section found in the three newest traces.\n'

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
