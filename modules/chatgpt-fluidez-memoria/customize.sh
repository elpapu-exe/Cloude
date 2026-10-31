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
for file in service.sh action.sh uninstall.sh bin/control.sh; do
  set_perm "$MODPATH/$file" 0 0 0755
done
ui_print '- Perfil experimental de memoria; no garantiza mas FPS.'
ui_print '- Conserva termicas, zRAM, LMKD y tus modulos.'
ui_print '- Reinicia para aplicar. Accion: pausar/restaurar o reactivar.'
ui_print '- Desactivar requiere reiniciar para retirar los efectos.'
