#!/system/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# One-shot WALT rate experiment. Fixed writable allowlist; identities are comparisons only.
PATH=/system/bin:/system/xbin:/vendor/bin:/data/adb/ksu/bin
export PATH
umask 077
MODDIR=$(CDPATH= cd "${0%/*}/.." && pwd) || exit 1
STATE=/data/adb/chatgpt-cpu-respuesta
SESSION=$STATE/session
LOG=$STATE/history.log
DOWNLOADS=/sdcard/Download
CPU=/sys/devices/system/cpu/cpufreq
MODE=${1:-status}
KEYS='policy0 policy4 global'
LOCK_HELD=false

say() { printf '%s\n' "$*"; }
log() { printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$LOG"; }
fail() { say "ERROR: $*"; exit 1; }
node_for() {
  case "$1" in
    policy0) printf '%s\n' "$CPU/policy0/walt/up_rate_limit_us";;
    policy4) printf '%s\n' "$CPU/policy4/walt/up_rate_limit_us";;
    global) printf '%s\n' "$CPU/walt/up_rate_limit_us";;
    *) return 1;;
  esac
}
number() {
  value=$1
  case "$value" in ''|*[!0-9]*) return 1;; esac
  [ "${#value}" -le 10 ] || return 1
  while [ "${value#0}" != "$value" ]; do value=${value#0}; done
  value=${value:-0}
  [ "${#value}" -le 7 ] && [ "$value" -le 1000000 ] || return 1
  printf '%s\n' "$value"
}
read_control() {
  read_node=$(node_for "$1") || return 1
  read_raw=$(timeout 3 cat "$read_node" 2>/dev/null) || return 1
  number "$read_raw"
}
identity() {
  canonical=$(timeout 3 readlink -f "$1" 2>/dev/null) || return 1
  case "$canonical" in /*) ;; *) return 1;; esac
  case "$canonical" in *[!A-Za-z0-9_./,:+-]*) return 1;; esac
  object=$(timeout 3 stat -L -c '%d:%i' "$1" 2>/dev/null) || return 1
  case "$object" in ''|*[!0-9:]*) return 1;; esac
  case "$object" in *:*) ;; *) return 1;; esac
  dev=${object%%:*}; ino=${object#*:}
  case "$dev:$ino" in :*|*:|*:*:*) return 1;; esac
  printf '%s %s\n' "$canonical" "$object"
}
probe() {
  probe_node=$(node_for "$1") || return 1
  [ -r "$probe_node" ] && [ -w "$probe_node" ] || return 1
  probe_value=$(read_control "$1") || return 1
  probe_identity=$(identity "$probe_node") || return 1
  printf '%s %s\n' "$probe_value" "$probe_identity"
}
is_walt() { [ "$(timeout 3 cat "$CPU/policy$1/scaling_governor" 2>/dev/null)" = walt ]; }
same_object() { [ "$1" = "$3" ] || [ "$2" = "$4" ]; }
supported_layout() {
  for layout_policy in "$CPU"/policy*; do
    [ -d "$layout_policy" ] || continue
    case "${layout_policy##*/}" in policy0|policy4) ;; *) return 1;; esac
  done
}
all_walt() {
  all_mask=
  for all_policy in "$CPU"/policy*; do
    [ -d "$all_policy" ] || continue
    case "${all_policy##*/}" in policy0) all_number=0;; policy4) all_number=4;; *) return 1;; esac
    is_walt "$all_number" || return 1
    all_mask=$all_mask$all_number
  done
  case "$all_mask" in 0|4|04) printf '%s\n' "$all_mask";; *) return 1;; esac
}
compatible() {
  [ "$(getprop ro.build.version.sdk)" = 33 ] || return 1
  case "$(uname -m)" in aarch64|arm64) ;; *) return 1;; esac
  case "$(uname -r)" in 5.15.*) ;; *) return 1;; esac
  for property in ro.product.device ro.product.vendor.device ro.product.system.device; do
    case "$(getprop "$property")" in tapas|topaz|lineage_tapas|lineage_topaz) return 0;; esac
  done
  return 1
}
unlock() {
  if [ "$LOCK_HELD" = true ]; then
    rm -f "$LOCK/pid" "$SESSION/plan.$$" "$SESSION"/*.tmp.$$
    rmdir "$LOCK" 2>/dev/null || :
  fi
}
init_state() {
  [ ! -L "$STATE" ] && [ ! -L "$SESSION" ] || fail 'Directorio de estado inesperado.'
  mkdir -p "$SESSION" || fail 'No se puede guardar el estado.'
  chmod 700 "$STATE" "$SESSION" || fail 'No se pueden proteger los registros.'
  for file in "$LOG" "$STATE/history.previous.log" "$STATE/paused" "$SESSION/boot" "$SESSION/format" "$SESSION/policy0" "$SESSION/policy4" "$SESSION/global"; do
    [ ! -L "$file" ] || fail 'Registro enlazado: no se modifica.'
    [ ! -e "$file" ] || [ -f "$file" ] || fail 'Registro con tipo inesperado.'
  done
  boot_id=$(timeout 3 cat /proc/sys/kernel/random/boot_id 2>/dev/null)
  case "$boot_id" in ''|*[!0-9a-fA-F-]*) fail 'No se identifica este arranque.';; esac
  [ "${#boot_id}" -eq 36 ] || fail 'Identidad de arranque inesperada.'
  LOCK=$STATE/lock.$boot_id
  mkdir "$LOCK" 2>/dev/null || fail 'Operacion activa o interrumpida: reinicia para liberar el bloqueo.'
  LOCK_HELD=true
  trap unlock 0
  trap 'exit 130' 1 2 15
  printf '%s\n' "$$" > "$LOCK/pid" || fail 'No se pudo registrar el bloqueo.'
  : >> "$LOG" || fail 'No se puede guardar el registro.'
  log_size=$(wc -c < "$LOG" | tr -d '[:space:]')
  case "$log_size" in ''|*[!0-9]*) fail 'Registro con tamano inesperado.';; esac
  if [ "$log_size" -gt 131072 ]; then mv "$LOG" "$STATE/history.previous.log" || fail 'No se pudo rotar el registro.'; fi
}
prepare_session() {
  if [ "$(cat "$SESSION/boot" 2>/dev/null)" != "$boot_id" ]; then
    rm -f "$SESSION/policy0" "$SESSION/policy4" "$SESSION/global" "$SESSION/format" || fail 'No se pudo preparar el arranque.'
    printf '%s\n' "$boot_id" > "$SESSION/boot" || fail 'No se pudo guardar el arranque.'
    printf '1\n' > "$SESSION/format" || fail 'No se pudo guardar el formato.'
    log "NEW_BOOT $boot_id; no se restauran valores de otro arranque."
  fi
  [ "$(cat "$SESSION/format" 2>/dev/null)" = 1 ] || fail 'Formato desconocido; conserva los registros.'
}
load_record() {
  [ -f "$SESSION/$1" ] && [ ! -L "$SESSION/$1" ] || return 1
  [ "$(wc -l < "$SESSION/$1" | tr -d '[:space:]')" = 1 ] || return 1
  IFS=' ' read -r saved_old saved_target saved_canonical saved_object saved_mask saved_p0 saved_id0 saved_p4 saved_id4 extra < "$SESSION/$1" || return 1
  [ -z "$extra" ] || return 1
  saved_old=$(number "$saved_old") && saved_target=$(number "$saved_target") || return 1
  [ "$saved_old" -ge 20001 ] && [ "$saved_old" -le 100000 ] || return 1
  [ "$saved_target" -eq "$(((saved_old * 3 + 3) / 4))" ] || return 1
  case "$saved_mask" in 0|4|04) ;; *) return 1;; esac
  case "$1:$saved_mask" in policy0:0|policy0:04|policy4:4|global:0|global:4|global:04) ;; *) return 1;; esac
  case "$saved_canonical" in /*) ;; *) return 1;; esac
  case "$saved_canonical$saved_p0$saved_p4" in *[!A-Za-z0-9_./,:+-]*) return 1;; esac
  case "$saved_object" in ''|*[!0-9:]*|:*|*:|*:*:*) return 1;; esac
  case "$saved_object" in *:*) ;; *) return 1;; esac
  for part in 0 4; do
    case "$part" in 0) path=$saved_p0; ident=$saved_id0;; 4) path=$saved_p4; ident=$saved_id4;; esac
    case "$saved_mask" in *"$part"*)
      case "$path" in /*) ;; *) return 1;; esac
      case "$ident" in ''|*[!0-9:]*|:*|*:|*:*:*) return 1;; esac
      case "$ident" in *:*) ;; *) return 1;; esac;;
      *) [ "$path" = - ] && [ "$ident" = - ] || return 1;;
    esac
  done
}
verify_context() {
  # Caller supplies validated journal/plan fields. They never select a write path.
  context_key=$1
  supported_layout || return 1
  context_node=$(node_for "$context_key") || return 1
  [ "$(identity "$context_node")" = "$saved_canonical $saved_object" ] || return 1
  for context_part in 0 4; do
    case "$saved_mask" in *"$context_part"*)
      is_walt "$context_part" || return 1
      case "$context_part" in 0) expected="$saved_p0 $saved_id0";; 4) expected="$saved_p4 $saved_id4";; esac
      [ "$(identity "$CPU/policy$context_part")" = "$expected" ] || return 1
      if [ "$context_key" != global ]; then
        [ "$(identity "$(node_for "policy$context_part")")" = "$saved_canonical $saved_object" ] || {
          # A hard link can have a different canonical name but the same object.
          context_other=$(timeout 3 stat -L -c '%d:%i' "$(node_for "policy$context_part")" 2>/dev/null)
          [ "$context_other" = "$saved_object" ] || return 1
        }
      fi;;
    esac
  done
  if [ "$context_key" = global ]; then
    [ "$(all_walt)" = "$saved_mask" ] || return 1
    for context_part in 0 4; do
      context_per=$(node_for "policy$context_part")
      if [ -e "$context_per" ]; then
        context_identity=$(identity "$context_per") || return 1
        IFS=' ' read -r context_canonical context_object <<EOD
$context_identity
EOD
        same_object "$context_canonical" "$context_object" "$saved_canonical" "$saved_object" || return 1
      fi
    done
  else
    # A new global or shared scope must not extend the recorded participants.
    context_global=$(node_for global)
    if [ -e "$context_global" ]; then return 1; fi
    for context_part in 0 4; do
      case "$saved_mask" in *"$context_part"*) continue;; esac
      context_other_node=$(node_for "policy$context_part") || return 1
      [ -e "$context_other_node" ] || continue
      context_identity=$(identity "$context_other_node") || return 1
      IFS=' ' read -r context_canonical context_object <<EOD
$context_identity
EOD
      same_object "$context_canonical" "$context_object" "$saved_canonical" "$saved_object" && return 1
    done
  fi
  return 0
}
emit_plan() {
  emit_key=$1; emit_old=$2; emit_canonical=$3; emit_object=$4; emit_mask=$5
  [ "$emit_old" -ge 20001 ] && [ "$emit_old" -le 100000 ] || { log "UNCHANGED $emit_key=$emit_old us; fuera del intervalo experimental."; return 0; }
  emit_p0=-; emit_id0=-; emit_p4=-; emit_id4=-
  case "$emit_mask" in *0*) emit_identity=$(identity "$CPU/policy0") || return 1; IFS=' ' read -r emit_p0 emit_id0 <<EOD
$emit_identity
EOD
  ;; esac
  case "$emit_mask" in *4*) emit_identity=$(identity "$CPU/policy4") || return 1; IFS=' ' read -r emit_p4 emit_id4 <<EOD
$emit_identity
EOD
  ;; esac
  printf '%s %s %s %s %s %s %s %s %s %s\n' "$emit_key" "$emit_old" "$(((emit_old * 3 + 3) / 4))" "$emit_canonical" "$emit_object" "$emit_mask" "$emit_p0" "$emit_id0" "$emit_p4" "$emit_id4" >> "$PLAN"
}
discover_plan() {
  PLAN=$SESSION/plan.$$
  (set -C; : > "$PLAN") || return 1
  supported_layout || { log 'SKIP: politica CPU fuera de policy0/policy4; scope no identificado.'; return 0; }
  data0=$(probe policy0) || data0=
  data4=$(probe policy4) || data4=
  datag=$(probe global) || datag=
  IFS=' ' read -r old0 canon0 obj0 <<EOD
$data0
EOD
  IFS=' ' read -r old4 canon4 obj4 <<EOD
$data4
EOD
  IFS=' ' read -r oldg canong objg <<EOD
$datag
EOD
  if [ -e "$(node_for global)" ]; then
    [ -n "$datag" ] || { log 'SKIP global: interfaz no legible/escribible o identidad no valida.'; return 0; }
    mask=$(all_walt) || { log 'SKIP global: no todas las politicas identificadas estan en WALT.'; return 0; }
    for scope in policy0 policy4; do
      case "$scope" in policy0) other_data=$data0; other_canon=$canon0; other_obj=$obj0; other_old=$old0;; policy4) other_data=$data4; other_canon=$canon4; other_obj=$obj4; other_old=$old4;; esac
      if [ -e "$(node_for "$scope")" ]; then
        [ -n "$other_data" ] && same_object "$other_canon" "$other_obj" "$canong" "$objg" && [ "$other_old" = "$oldg" ] || {
          log 'SKIP: scopes global/per-policy ambiguos o valor compartido cambiado.'; return 0;
        }
      fi
    done
    emit_plan global "$oldg" "$canong" "$objg" "$mask"
    return "$?"
  fi
  if [ -n "$data0" ] && [ -n "$data4" ] && same_object "$canon0" "$obj0" "$canon4" "$obj4"; then
    is_walt 0 && is_walt 4 && [ "$old0" = "$old4" ] || { log 'SKIP alias: gobernador o valor compartido ambiguo.'; return 0; }
    emit_plan policy0 "$old0" "$canon0" "$obj0" 04
    return "$?"
  fi
  if [ -n "$data0" ] && is_walt 0; then emit_plan policy0 "$old0" "$canon0" "$obj0" 0 || return 1; fi
  if [ -n "$data4" ] && is_walt 4; then emit_plan policy4 "$old4" "$canon4" "$obj4" 4 || return 1; fi
}
write_control() {
  fixed_node=$(node_for "$1") || return 1
  timeout 12 sh -c 'printf "%s" "$1" > "$2"' sh "$2" "$fixed_node" 2>> "$LOG"
}
apply_plan() {
  # Validate every existing record before any write; never apply 25% repeatedly.
  for prior in $KEYS; do
    [ ! -e "$SESSION/$prior" ] || load_record "$prior" || return 1
  done
  while IFS=' ' read -r plan_key plan_old plan_target plan_canonical plan_object plan_mask plan_p0 plan_id0 plan_p4 plan_id4; do
    already=false
    for prior in $KEYS; do
      [ -e "$SESSION/$prior" ] || continue
      load_record "$prior" || return 1
      if [ "$prior" = "$plan_key" ] || same_object "$saved_canonical" "$saved_object" "$plan_canonical" "$plan_object"; then already=true; fi
    done
    if [ "$already" = true ]; then log "KEEP $plan_key: journal existente; no se vuelve a reducir."; continue; fi
    saved_old=$plan_old; saved_target=$plan_target; saved_canonical=$plan_canonical; saved_object=$plan_object
    saved_mask=$plan_mask; saved_p0=$plan_p0; saved_id0=$plan_id0; saved_p4=$plan_p4; saved_id4=$plan_id4
    verify_context "$plan_key" || { log "SKIP $plan_key: identidad, scope o gobernador cambiados."; continue; }
    current=$(read_control "$plan_key") || return 1
    [ "$current" = "$plan_old" ] || { log "CONFLICT $plan_key: valor cambiado despues del plan; se conserva."; continue; }
    printf '%s %s %s %s %s %s %s %s %s\n' "$plan_old" "$plan_target" "$plan_canonical" "$plan_object" "$plan_mask" "$plan_p0" "$plan_id0" "$plan_p4" "$plan_id4" > "$SESSION/$plan_key.tmp.$$" || return 1
    mv "$SESSION/$plan_key.tmp.$$" "$SESSION/$plan_key" || return 1
    # Recheck after journaling, immediately before the fixed-path write.
    verify_context "$plan_key" && [ "$(read_control "$plan_key")" = "$plan_old" ] || {
      log "CONFLICT $plan_key antes de escribir; journal conservado."; continue;
    }
    write_control "$plan_key" "$plan_target"; write_result=$?
    observed=$(read_control "$plan_key")
    if [ "$observed" = "$plan_target" ]; then
      log "APPLIED $plan_key: $plan_old -> $observed us (escritura $write_result)."
      [ "$write_result" -eq 0 ] || return 1
    else
      [ "$observed" != "$plan_old" ] || rm -f "$SESSION/$plan_key"
      log "ERROR $plan_key: objetivo=$plan_target lectura=${observed:-NA} escritura=$write_result."
      return 1
    fi
  done < "$PLAN"
}
restore_controls() {
  restore_result=0
  [ "$(cat "$SESSION/boot" 2>/dev/null)" = "$boot_id" ] || { log 'SKIP_RESTORE: otro arranque.'; return 0; }
  [ "$(cat "$SESSION/format" 2>/dev/null)" = 1 ] || return 1
  for restore_key in $KEYS; do
    [ -e "$SESSION/$restore_key" ] || continue
    load_record "$restore_key" || { log "ERROR journal $restore_key; se conserva."; restore_result=1; continue; }
    verify_context "$restore_key" || { log "PRESERVED $restore_key: nodo/politica/scope/gobernador cambiados."; continue; }
    current=$(read_control "$restore_key") || { restore_result=1; continue; }
    if [ "$current" != "$saved_target" ]; then
      log "PRESERVED $restore_key=$current; difiere de nuestro objetivo $saved_target."
      continue
    fi
    verify_context "$restore_key" && [ "$(read_control "$restore_key")" = "$saved_target" ] || { restore_result=1; continue; }
    write_control "$restore_key" "$saved_old"; write_result=$?
    observed=$(read_control "$restore_key")
    if [ "$observed" = "$saved_old" ]; then
      log "RESTORED $restore_key: $saved_target -> $observed us."
      rm -f "$SESSION/$restore_key"
      [ "$write_result" -eq 0 ] || restore_result=1
    else
      log "ERROR restaurar $restore_key: lectura=${observed:-NA} escritura=$write_result."
      restore_result=1
    fi
  done
  return "$restore_result"
}
status() {
  [ ! -e "$STATE/paused" ] || say 'Perfil PAUSADO.'
  for status_key in $KEYS; do
    status_value=$(read_control "$status_key") || status_value=NA
    say "$status_key up_rate_limit_us: $status_value"
  done
  say "Registro: $LOG"
}
export_report() {
  log "REPORT kernel=$(uname -r)"
  report_path=$DOWNLOADS/ChatGPT-CPU-Respuesta-$(date -u '+%Y%m%d-%H%M%S')-$$.txt
  if [ -d "$DOWNLOADS" ] && (set -C; cat "$LOG" > "$report_path") 2>/dev/null; then say "Informe: $report_path"; else say "Registro privado: $LOG"; fi
}
apply_profile() {
  compatible || { log 'ERROR dispositivo/Android/kernel fuera del alcance.'; return 1; }
  [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ] || { log 'SKIP modulo desactivado/retirado.'; return 1; }
  prepare_session
  rm -f "$STATE/paused" || return 1
  discover_plan || { log 'ERROR no se pudo capturar el plan completo; no se escribe.'; return 1; }
  apply_plan; result=$?
  if [ "$result" -eq 0 ]; then say 'Revision CPU terminada; los controles no elegibles se omiten. Consulta status o el registro.'; else say 'Aplicacion incompleta: consulta el registro y usa restore o reinicia sin el modulo.'; fi
  return "$result"
}

[ "$(id -u)" = 0 ] || fail 'Se requiere root KernelSU.'
command -v timeout >/dev/null 2>&1 || fail 'No hay timeout: no se aplican ajustes.'
case "$MODE" in apply|restore|status|report|toggle|boot|uninstall) ;; *) fail 'Uso: control.sh apply|restore|status|report|toggle|boot|uninstall';; esac
if [ "$MODE" = boot ]; then
  compatible || exit 1
  attempts=0
  while [ "$(getprop sys.boot_completed)" != 1 ]; do
    attempts=$((attempts + 1)); [ "$attempts" -lt 90 ] || exit 1
    [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ] || exit 0
    sleep 2
  done
  sleep 15
fi
init_state
case "$MODE" in
  apply) apply_profile; exit "$?";;
  boot)
    if [ -e "$STATE/paused" ] || [ -e "$MODDIR/disable" ] || [ -e "$MODDIR/remove" ]; then log 'SKIP_BOOT pausado/desactivado/retirado.'; exit 0; fi
    apply_profile; exit "$?";;
  restore)
    : > "$STATE/paused" || fail 'No se pudo guardar la pausa.'
    restore_controls; result=$?; status; export_report; exit "$result";;
  toggle)
    if [ -e "$STATE/paused" ]; then apply_profile; result=$?; else : > "$STATE/paused" || fail 'No se pudo pausar.'; restore_controls; result=$?; fi
    status; export_report; exit "$result";;
  status) status;;
  report) status; export_report;;
  uninstall)
    : > "$STATE/paused" || fail 'No se pudo pausar.'
    restore_controls || { say 'Se conservan registros: reinicia con el modulo desactivado.'; exit 1; }
    # Preserve any unresolved journal rather than silently discarding recovery data.
    for remaining in $KEYS; do
      if [ -e "$SESSION/$remaining" ]; then say 'Se conservan registros de cambios ajenos o identidades antiguas.'; exit 0; fi
    done
    rm -rf "$STATE"
    say 'Controles propios retirados.';;
esac
