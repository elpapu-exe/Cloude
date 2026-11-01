#!/system/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
[ "$KSU" = true ] || abort 'Instala este ZIP desde KernelSU/ReSukiSU.'
[ "$(getprop ro.build.version.sdk)" = 33 ] || abort 'Esta prueba requiere Android 13.'
case "$(uname -m)" in aarch64|arm64) ;; *) abort 'Se requiere ARM64.';; esac
case "$(uname -r)" in 5.15.*) ;; *) abort 'Esta prueba requiere el kernel 5.15 del dispositivo.';; esac
compatible=false
for prop in ro.product.device ro.product.vendor.device ro.product.system.device; do
  case "$(getprop "$prop")" in tapas|topaz|lineage_tapas|lineage_topaz) compatible=true;; esac
done
[ "$compatible" = true ] || abort 'Solo Redmi Note 12 4G TAPAS/topaz.'
set_perm_recursive "$MODPATH" 0 0 0755 0644
for file in service.sh action.sh uninstall.sh bin/control.sh bin/collect.sh; do
  set_perm "$MODPATH/$file" 0 0 0755
done
ui_print '- Prueba CPU condicional, sin garantia de mayor fluidez.'
ui_print '- Solo WALT up_rate_limit_us de 20001 a 100000 us: recorte del 25%.'
ui_print '- Si ya usa 500-2000 us, no cambia ese valor.'
ui_print '- No modifica GPU, memoria, zRAM, frecuencias ni termicas.'
ui_print '- Accion recoge logs durante 180 s; no pausa ni reactiva el perfil.'
ui_print '- Para retirar efectos: control.sh restore, o desactivar y reiniciar.'
