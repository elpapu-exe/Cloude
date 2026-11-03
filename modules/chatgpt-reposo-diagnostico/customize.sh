#!/system/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
[ "$KSU" = true ] || abort 'Instala este ZIP desde KernelSU/ReSukiSU.'
[ "$(id -u)" = 0 ] || abort 'Se necesita root para leer el diagnóstico.'
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/bin/collect.sh" 0 0 0755
ui_print '- Diagnóstico de reposo, sin cambiar ajustes del teléfono.'
ui_print '- Acción: primera pulsación inicia; segunda finaliza y guarda TXT.'
ui_print '- No queda ningún proceso esperando entre pulsaciones.'
ui_print '- Si Acción no aparece tras instalar, reinicia una vez.'
