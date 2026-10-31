#!/system/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Finite, journaled control changes. No mounting, daemon or policy enforcement.
PATH=/system/bin:/system/xbin:/vendor/bin:/data/adb/ksu/bin
export PATH
umask 077
MODDIR=$(CDPATH= cd "${0%/*}/.." && pwd) || exit 1
STATE=/data/adb/chatgpt-fluidez-memoria
SESSION=$STATE/session
LOG=$STATE/history.log
DOWNLOADS=/sdcard/Download
MODE=${1:-status}
KEYS='mglru watermark'
LOCK_HELD=false

say() { printf '%s\n' "$*"; }
log() { printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$LOG"; }
fail() { say "ERROR: $*"; exit 1; }
node_for() {
  case "$1" in
    mglru) printf '%s\n' /sys/kernel/mm/lru_gen/enabled;;
    watermark) printf '%s\n' /proc/sys/vm/watermark_scale_factor;;
    *) return 1;;
  esac
}
number() {
  numeric_value=$2
  [ -n "$numeric_value" ] || return 1
  case "$1" in
    mglru)
      [ "${#numeric_value}" -le 10 ] || return 1
      case "$numeric_value" in
        0x*|0X*) numeric_value=${numeric_value#??}; [ -n "$numeric_value" ] || return 1;;
      esac
      while [ "${numeric_value#0}" != "$numeric_value" ]; do numeric_value=${numeric_value#0}; done
      numeric_value=${numeric_value:-0}
      case "$numeric_value" in [0-7]) ;; *) return 1;; esac;;
    watermark)
      [ "${#numeric_value}" -le 4 ] || return 1
      case "$numeric_value" in *[!0-9]*) return 1;; esac
      while [ "${numeric_value#0}" != "$numeric_value" ]; do numeric_value=${numeric_value#0}; done
      numeric_value=${numeric_value:-0}
      [ "$numeric_value" -ge 1 ] && [ "$numeric_value" -le 3000 ] || return 1;;
    *) return 1;;
  esac
  printf '%s\n' "$numeric_value"
}
read_control() {
  control_node=$(node_for "$1") || return 1
  control_raw=$(timeout 3 cat "$control_node" 2>/dev/null) || return 1
  number "$1" "$control_raw"
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
    rm -f "$LOCK/pid"
    rmdir "$LOCK" 2>/dev/null || :
  fi
}
init_state() {
  [ ! -L "$STATE" ] && [ ! -L "$SESSION" ] || fail 'Directorio de estado inesperado.'
  mkdir -p "$SESSION" || fail 'No se puede guardar el estado.'
  chmod 700 "$STATE" "$SESSION" || fail 'No se pueden proteger los registros.'
  for file in "$LOG" "$STATE/paused" "$SESSION/boot" "$SESSION/format" "$SESSION/mglru" "$SESSION/watermark"; do
    [ ! -L "$file" ] || fail 'Registro enlazado: no se modifica.'
    [ ! -e "$file" ] || [ -f "$file" ] || fail 'Registro con tipo inesperado.'
  done
  boot_id=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
  case "$boot_id" in ''|*[!0-9a-fA-F-]*) fail 'No se identifica este arranque.';; esac
  [ "${#boot_id}" -eq 36 ] || fail 'Identidad de arranque inesperada.'
  LOCK=$STATE/lock.$boot_id
  mkdir "$LOCK" 2>/dev/null || fail 'Operacion ya activa o interrumpida. Reinicia para limpiar el bloqueo.'
  LOCK_HELD=true
  trap unlock 0
  trap 'exit 130' 1 2 15
  printf '%s\n' "$$" > "$LOCK/pid" || fail 'No se pudo registrar el bloqueo.'
  : >> "$LOG" || fail 'No se puede guardar el registro.'
  if [ -f "$LOG" ]; then
    log_size=$(wc -c < "$LOG" | tr -d '[:space:]')
    case "$log_size" in *[!0-9]*) :;; *)
      if [ "$log_size" -gt 131072 ]; then mv "$LOG" "$STATE/history.previous.log" || fail 'No se pudo rotar el registro.'; fi;;
    esac
  fi
}
prepare_session() {
  recorded_boot=$(cat "$SESSION/boot" 2>/dev/null)
  if [ "$recorded_boot" != "$boot_id" ]; then
    rm -f "$SESSION/mglru" "$SESSION/watermark" "$SESSION/format" || fail 'No se puede preparar el registro del arranque.'
    printf '%s\n' "$boot_id" > "$SESSION/boot" || fail 'No se puede guardar este arranque.'
    printf '1\n' > "$SESSION/format" || fail 'No se puede guardar el formato.'
    log "NEW_BOOT $boot_id; las restauraciones antiguas no se aplican."
  fi
  [ "$(cat "$SESSION/format" 2>/dev/null)" = 1 ] || fail 'Formato de estado desconocido; conserva los registros y reinicia sin el modulo.'
}
load_record() {
  [ -f "$SESSION/$1" ] && [ ! -L "$SESSION/$1" ] || return 1
  IFS=' ' read -r saved_old saved_target extra < "$SESSION/$1" || return 1
  [ -z "$extra" ] || return 1
  saved_old=$(number "$1" "$saved_old") || return 1
  saved_target=$(number "$1" "$saved_target") || return 1
  case "$1" in
    mglru) [ "$((saved_old & 1))" -eq 0 ] && [ "$saved_target" -eq "$((saved_old | 1))" ] || return 1;;
    watermark) [ "$saved_old" -lt 64 ] && [ "$saved_target" -eq 64 ] || return 1;;
  esac
}
write_control() {
  write_node=$(node_for "$1") || return 1
  timeout 12 sh -c 'printf "%s" "$1" > "$2"' sh "$2" "$write_node" 2>> "$LOG"
}
apply_one() {
  apply_key=$1
  current=$(read_control "$apply_key") || { log "SKIP $apply_key: interfaz ausente o lectura no valida."; return 0; }
  if [ -e "$SESSION/$apply_key" ]; then
    load_record "$apply_key" || { log "ERROR $apply_key: registro no valido."; return 1; }
    if [ "$current" = "$saved_target" ]; then
      log "KEEP $apply_key=$current; original conservado: $saved_old."
    else
      log "CONFLICT $apply_key=$current; otro cambio posterior se conserva."
    fi
    return 0
  fi
  case "$apply_key" in
    mglru) [ "$((current & 1))" -eq 0 ] || { log "UNCHANGED mglru=$current; ya activo."; return 0; }; target=$((current | 1));;
    watermark) [ "$current" -lt 64 ] || { log "UNCHANGED watermark=$current; no se reduce."; return 0; }; target=64;;
  esac
  # Compare again immediately before journaling; procfs does not provide atomic CAS.
  verified=$(read_control "$apply_key") || return 1
  [ "$verified" = "$current" ] || { log "CONFLICT $apply_key cambio durante la lectura; se omite."; return 0; }
  printf '%s %s\n' "$current" "$target" > "$SESSION/$apply_key.tmp.$$" || return 1
  mv "$SESSION/$apply_key.tmp.$$" "$SESSION/$apply_key" || return 1
  write_control "$apply_key" "$target"
  write_result=$?
  observed=$(read_control "$apply_key")
  if [ "$observed" = "$target" ]; then
    log "APPLIED $apply_key: $current -> $observed (escritura $write_result)."
    [ "$write_result" -eq 0 ] || { log "ERROR $apply_key: escritura con error pese al valor aplicado; journal conservado."; return 1; }
    return 0
  fi
  [ "$observed" != "$current" ] || rm -f "$SESSION/$apply_key"
  log "ERROR $apply_key: objetivo=$target lectura=${observed:-NA} escritura=$write_result."
  return 1
}
restore_controls() {
  restore_result=0
  [ "$(cat "$SESSION/boot" 2>/dev/null)" = "$boot_id" ] || { log 'SKIP_RESTORE: pertenece a otro arranque.'; return 0; }
  [ "$(cat "$SESSION/format" 2>/dev/null)" = 1 ] || { log 'ERROR restaurar: formato desconocido; se conservan los datos.'; return 1; }
  for restore_key in $KEYS; do
    [ -e "$SESSION/$restore_key" ] || continue
    if ! load_record "$restore_key"; then log "ERROR restaurar $restore_key: registro no valido."; restore_result=1; continue; fi
    current=$(read_control "$restore_key") || { log "ERROR lectura restaurar $restore_key."; restore_result=1; continue; }
    if [ "$current" != "$saved_target" ]; then
      log "PRESERVED $restore_key=$current; difiere del aplicado $saved_target."
      rm -f "$SESSION/$restore_key"
      continue
    fi
    verified=$(read_control "$restore_key") || { restore_result=1; continue; }
    [ "$verified" = "$saved_target" ] || { log "CONFLICT restaurar $restore_key; se omite."; restore_result=1; continue; }
    write_control "$restore_key" "$saved_old"
    write_result=$?
    observed=$(read_control "$restore_key")
    if [ "$observed" = "$saved_old" ]; then
      log "RESTORED $restore_key: $saved_target -> $observed."
      rm -f "$SESSION/$restore_key"
      [ "$write_result" -eq 0 ] || { log "WARNING restaurar $restore_key: valor original leido, escritura con error $write_result."; restore_result=1; }
    else
      log "ERROR restaurar $restore_key: lectura=${observed:-NA} escritura=$write_result; reinicia con el modulo pausado."
      restore_result=1
    fi
  done
  return "$restore_result"
}
read_snapshot() {
  log "SNAPSHOT $1 kernel=$(uname -r)"
  {
    printf 'UTC: '; date -u '+%Y-%m-%dT%H:%M:%SZ'
    printf 'uptime: '; timeout 3 cat /proc/uptime 2>/dev/null
    for key in $KEYS; do printf '%s: ' "$key"; read_control "$key" || printf 'NA\n'; done
    timeout 3 cat /proc/meminfo 2>/dev/null | grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree|CmaTotal|CmaFree):'
    for pressure in memory cpu io; do printf 'PSI %s: ' "$pressure"; timeout 3 cat "/proc/pressure/$pressure" 2>/dev/null; done
    timeout 3 cat /proc/vmstat 2>/dev/null | grep -E '^(pswpin|pswpout|pgmajfault|allocstall[^ ]*|pgscan[^ ]*|pgsteal[^ ]*|workingset_refault[^ ]*|kswapd_low_wmark_hit_quickly|oom_kill) '
    printf 'battery_temp_tenths_C: '; timeout 3 cat /sys/class/power_supply/battery/temp 2>/dev/null
    for field in disksize comp_algorithm mm_stat; do printf 'zram0/%s: ' "$field"; timeout 3 cat "/sys/block/zram0/$field" 2>/dev/null; done
    for policy in /sys/devices/system/cpu/cpufreq/policy*; do
      [ -d "$policy" ] || continue
      printf '%s governor/current/max_kHz: ' "${policy##*/}"
      for field in scaling_governor scaling_cur_freq scaling_max_freq; do timeout 3 cat "$policy/$field" 2>/dev/null; done
    done
  } >> "$LOG"
  return 0
}
status() {
  if [ -f "$STATE/paused" ]; then say 'Perfil PAUSADO.'; else say 'Perfil habilitado para este arranque (comprueba valores y registro).'; fi
  for key in $KEYS; do
    current=$(read_control "$key") || current=NA
    say "$key actual: $current"
  done
  say "Registro: $LOG"
}
export_report() {
  read_snapshot REPORT
  report_path=$DOWNLOADS/ChatGPT-Fluidez-$(date -u '+%Y%m%d-%H%M%S')-$$.txt
  if [ -d "$DOWNLOADS" ] && (set -C; cat "$LOG" > "$report_path") 2>/dev/null; then
    say "Informe: $report_path"
  else
    say "No se pudo exportar en Descargas; registro privado: $LOG"
  fi
}
apply_profile() {
  compatible || { log 'ERROR dispositivo/Android/kernel fuera del alcance.'; say 'Dispositivo no compatible: no se cambian ajustes.'; return 1; }
  [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ] || { log 'SKIP: modulo desactivado o marcado para retirar.'; return 1; }
  prepare_session
  rm -f "$STATE/paused" || fail 'No se pudo reactivar de forma persistente.'
  read_snapshot BEFORE_APPLY
  apply_result=0
  for key in $KEYS; do apply_one "$key" || apply_result=1; done
  read_snapshot AFTER_APPLY
  if [ "$apply_result" -eq 0 ]; then say 'Revision terminada. Consulta los valores actuales; las interfaces ausentes se omiten.'; else say 'Aplicacion incompleta: revisa el registro. Puedes pausar o reiniciar sin el modulo.'; fi
  return "$apply_result"
}

[ "$(id -u)" = 0 ] || fail 'Se requiere root KernelSU.'
command -v timeout >/dev/null 2>&1 || fail 'No hay timeout disponible; no se aplican ajustes.'
case "$MODE" in apply|restore|toggle|status|report|boot|uninstall) ;; *) fail 'Uso: control.sh apply|restore|toggle|status|report|boot|uninstall';; esac
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
  boot)
    if [ -e "$STATE/paused" ] || [ -e "$MODDIR/disable" ] || [ -e "$MODDIR/remove" ]; then log 'SKIP_BOOT: pausado/desactivado/retirado.'; exit 0; fi
    apply_profile; exit "$?";;
  apply) apply_profile; exit "$?";;
  restore)
    : > "$STATE/paused" || fail 'No se pudo guardar la pausa; no se anuncian valores restaurados.'
    read_snapshot BEFORE_RESTORE
    restore_controls; operation_result=$?
    read_snapshot AFTER_RESTORE
    status; export_report
    exit "$operation_result";;
  toggle)
    if [ -f "$STATE/paused" ]; then
      apply_profile; operation_result=$?
    else
      : > "$STATE/paused" || fail 'No se pudo guardar la pausa.'
      read_snapshot BEFORE_RESTORE
      restore_controls; operation_result=$?
      read_snapshot AFTER_RESTORE
      if [ "$operation_result" -eq 0 ]; then say 'Perfil pausado; valores propios restaurados o cambios posteriores conservados.'; else say 'Restauracion incompleta. Reinicia con el modulo pausado.'; fi
    fi
    status; export_report
    exit "$operation_result";;
  status) status;;
  report) status; export_report;;
  uninstall)
    : > "$STATE/paused" || fail 'No se pudo guardar la pausa; no se anuncian valores restaurados.'
    restore_controls; operation_result=$?
    if [ "$operation_result" -ne 0 ]; then say 'No se retiran los registros pendientes. Reinicia sin el modulo.'; exit 1; fi
    rm -rf "$STATE"
    say 'Ajustes propios retirados. Si esta sesion era de otro arranque, no se restauraron valores antiguos.';;
esac
