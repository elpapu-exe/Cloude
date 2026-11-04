# Cuarto informe: bloqueo UART sostenido durante una carga prolongada

El informe rc2 termina con TEST FINISHED. Entre START y END transcurren 42735,98 s, aproximadamente 11 h 52 min, y la batería pasa de 18 a 100%. Los extremos están desenchufados, pero el intervalo incluye una carga. No se publica el TXT original ni su inventario de aplicaciones.

## Hallazgo concreto

La fuente kernel `4a8c000.qcom,qup_uart` permanece Active en ambos extremos. Conserva active/event count 15 y la misma última transición. Su tiempo activo aumenta de 10549308 a 53284941 ms: **42735,633 s adicionales**, prácticamente todo el intervalo. Ya estaba activa antes de conectar la carga y seguía activa en la captura final sin cable.

El USB `4e00000.ssusb` añade 42703,192 s de actividad, con una activación nueva entre capturas. Es consistente con permanecer conectado a carga/USB casi toda la noche; aparece inactivo en ambos extremos. No se presenta la actividad USB durante una carga como prueba de un bug por sí sola.

La lectura de wakeup_count no produce un valor numérico. El kernel puede bloquear esa lectura hasta que no haya eventos activos; el recolector la limita con timeout. No significa un contador cero. Una fuente sostenida puede impedir avanzar hacia nuevos intentos de suspensión. Los intentos permanecen en 1478 y los fallos en 171: no hay nuevos fallos de freezer, ICNSS o QRTR contabilizados durante este tramo.

El incremento de CLOCK_MONOTONIC es 42735,9708 s y el de BOOTTIME es 42735,98 s, sin suspensión adicional apreciable a esa resolución. Esto no es una prueba de diez minutos de descarga ni debe compararse directamente con los porcentajes de los informes cortos.

## Qué no permite concluir sobre aplicaciones

Batterystats reinició su periodo durante la carga. El comienzo corresponde al periodo anterior; el final solo contiene 18,476 s después de desconectar. No se restan los contadores UID entre esos periodos.

La fila de Picsart al inicio conserva exactamente los 7 min 0,656 s observados al final del informe anterior: ese tiempo no es actividad nueva de esta noche. No aumentó entre el informe anterior y este START, bajo el mismo periodo contable. La ausencia de fila al END, después del reinicio contable, no demuestra por sí sola qué ocurrió durante todo el intervalo. Los bloqueos finales de Instagram de unos cinco segundos tampoco explican las horas intermedias.

Los bloqueos Display/interactive y pantalla despierta de las capturas son estados puntuales. Display solo añade unos 205 s; no se afirma que el usuario mantuviera la pantalla encendida doce horas. Nuestros perfiles CPU/memoria siguen desactivados y watermark vale 1.

## Dato HAL inválido

`total suspend time=27670120524822 ms` ya era imposible al START y permanece idéntico al END. No se usa como duración real. Su patrón numérico sugiere un problema de conversión o acumulación, sin causa demostrada.

El archivo last_suspend_time contiene el último ciclo, no un acumulado: 0,176878924 s de transición y 3,046044373 s de sueño, idénticos en ambos extremos. La exportación de duraciones firmadas con formato unsigned en wakeup_reason.c merece revisión separada; sin una muestra defectuosa o código HAL exacto no se afirma que origine el contador imposible ni el wakelock UART.

## Siguiente comprobación específica

En el código GENI serial, runtime_resume mantiene la fuente de despertar mientras el puerto está activo; runtime_suspend la libera al completar la suspensión. Ese contrato no demuestra un bug: falta conocer el cliente, el estado runtime PM y por qué no se suspende. La receta vendor admite el módulo; la configuración Image no incorpora esa implementación como parte del Image.

Un árbol público de topaz asigna ttyHS0/ttyHS2 a Bluetooth. No es una identificación del DT ni de la ROM exacta del teléfono, así que Bluetooth es una hipótesis para comprobar, no un culpable demostrado. Se solicitó al usuario confirmar Bluetooth y accesorios durante el intervalo.

Si Bluetooth está encendido: con USB/cargador desconectados, iniciar el mismo recolector, apagar Bluetooth temporalmente y dejar la pantalla apagada unos diez minutos; después finalizar. Mantener Wi-Fi/datos para WhatsApp y conservar módulos necesarios. La prueba busca verificar si UART deja de estar Active y vuelve la suspensión; no precisa otro kernel, módulo o reinicio. Si Bluetooth ya estaba apagado, no se repite un cambio inexistente: falta identificar el cliente real de UART.

Referencias revisadas:

- [Lectura bloqueante de wakeup_count](../kernel-source/linux/kernel/power/main.c).
- [Conteo de eventos activos](../kernel-source/linux/drivers/base/power/wakeup.c).
- [Runtime PM y wakelock GENI serial](../kernel-source/linux/drivers/tty/serial/msm_geni_serial.c).
- [Último ciclo y formato de wakeup_reason](../kernel-source/linux/kernel/power/wakeup_reason.c).
- [Configuración pública topaz, referencia de Bluetooth y ttyHS](https://github.com/eternyx404/device_xiaomi_topaz/blob/ef8b7b823abd46ed12338e6c684f4633260834a4/rootdir/etc/init.qcom.rc).
