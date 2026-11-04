# Investigación de reposo con rc5

**Cuarto informe:** intervalo de casi doce horas con carga 18 → 100%, reinicio de batterystats y una fuente UART activa prácticamente todo el tramo. Los siete minutos de Picsart al inicio son históricos y no se atribuyen a esta noche. [Hallazgo UART, límites y prueba específica](suspend-result-uart.md). Se mantiene el recolector existente; no se aplican bloqueadores de wakelocks ni cambios de kernel.

**Tercer informe, con rc2 del diagnóstico:** solo 11,29 s de suspensión en 620,58 s, batería 40 → 41 °C y captura iniciada a los 62 s del arranque. Picsart es la mayor atribución nueva de bloqueo parcial de aplicación; el usuario confirmó que no lo utilizaba. [Datos, límites y cambio específico](suspend-result-picsart.md). Los dos perfiles experimentales ya están desactivados y no se necesita otra versión del recolector para comprobar esta aplicación.

**Primer informe analizado:** hubo 12 min 37 s de suspensión en 21 min 43 s y la batería pasó de 40 a 37 °C. Aparecen fallos de suspensión de Wi-Fi, temporizadores pendientes y bloqueos parciales Android. [Resultados y límites](suspend-result-20261103.md). La captura inicial siguiente conserva su contexto histórico.

**Segundo informe:** 7 min 13 s de suspensión en 16 min 26 s (44%), batería 38 → 38 °C. No aumentan los fallos ICNSS/WLAN, pero sí los abortos y fallos de freeze; además watermark cambió de 1 a 64. [Comparación y límites](suspend-comparison-20261103.md). Se publicó rc2 del diagnóstico con atribución por UID y mejor conservación de mensajes, sin cambios de kernel ni ajustes del teléfono.

La captura recibida identifica `5.15.216-ChatGPTKernel-0.1.0-rc5`, 13 h 26 min 57 s de uptime y 8 min 57 s de deep sleep indicado por la aplicación, aproximadamente 1,1% acumulado. La batería muestra 44 °C y descarga instantánea de 307 mA, con la pantalla encendida para la captura. La carga 6,90 incluye tareas ejecutables y esperas no interrumpibles; no es un porcentaje CPU. Tampoco conocemos cuánto tiempo estuvo apagada la pantalla. La zRAM mostrada es de 2047 MiB lógicos.

Esto confirma arranque de una versión identificada como rc5 y justifica investigar reposo/consumo. No demuestra la causa, la identidad binaria exacta instalada ni una regresión causal frente a otro kernel. Los resultados de compilación históricos conservan su alcance original.

## Medidas inmediatas y reversibles

Deja el teléfono desenchufado y sin carga de trabajo para enfriarse. Si instalaste nuestro módulo experimental CPU Respuesta, desactívalo y reinicia durante este diagnóstico; conserva la ROM, WhatsApp y los módulos personales necesarios. Mantén las protecciones térmicas. Evita redimensionar zRAM mientras está caliente y bajo carga.

En la barra de estado se observa un icono de emisión. Si hay una grabación o transmisión de pantalla activa, termina esa sesión antes de medir. El icono por sí solo no identifica un bloqueo ni su propietario.

Si rc5 sigue funcionando peor o calentándose en reposo después de reiniciar, puedes restaurar tu boot anterior verificado siguiendo [la guía de recuperación](installation.md). Si el aparato permanece caliente estando **completamente apagado y desconectado**, la prueba de suspensión de Android no aplica; requiere evaluar también batería/carga/hardware.

## Un TXT, dos pulsaciones

El nuevo módulo **ChatGPT Reposo Diagnóstico** contiene exclusivamente un recolector. Su instalación y uso se documentan en [INSTRUCCIONES.txt](../modules/chatgpt-reposo-diagnostico/INSTRUCCIONES.txt). **[Descargar ZIP rc2 — 16,4 KB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-reposo-diagnostico-0.1.0-rc2-9d6ab6d12c08-41702509577/ChatGPT-Reposo-Diagnostico-0.1.0-rc2-KSU.zip)** · [Hashes y fuentes](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-reposo-diagnostico-0.1.0-rc2-9d6ab6d12c08-41702509577) · [Evidencia rc2](reposo-module-release-rc2.json). Publicado por Actions después de 21 pruebas sin omisiones y de descargar y verificar sus cinco assets. La actualización sirve para obtener evidencia y no aplica ajustes de reposo. Las fuentes también ejecutaron las 21 pruebas de forma independiente.

1. Actualiza el módulo desde KernelSU. Durante esta captura deja desactivados nuestros perfiles CPU Respuesta y Fluidez Memoria, y reinicia para retirar sus efectos. Conserva todos tus módulos personales necesarios. No hay scripts de arranque, servicios ni ajustes en el diagnóstico.
2. Con el cargador y USB desconectados, pulsa **Acción** y espera **START SAVED**. Al terminar, el recolector sale por completo.
3. Apaga la pantalla unos **diez minutos**, sin usar el teléfono. Conserva tu conexión habitual, WhatsApp y módulos necesarios; mantén los mismos ajustes durante el intervalo.
4. Desbloquea y pulsa **Acción** otra vez. Espera **TEST FINISHED** y comparte `Download/ChatGPT-Reposo-*.txt`.

Ese intervalo incluye el breve tiempo de operar el recolector; no se supone que todo él fuera pantalla apagada. El informe recoge relojes, batería, fuentes de wakeup, intentos/fallos de suspensión disponibles, bloqueos de Android, proyección de pantalla, CPU/GPU, PSI y contadores de reclaim/swap. Solo captura nombres/tiempo de procesos, no argumentos, mensajes o notificaciones. El formato de proyección se filtra según Android 13. Puede contener nombres de apps y wakelocks; revísalo antes de compartirlo. No se transmite nada automáticamente.

No usa un bucle de muestreo, `sleep`, alarma, wakelock ni un proceso esperando entre pulsaciones. La suspensión aproximada se calcula por diferencia de CLOCK_BOOTTIME (`/proc/uptime`) y CLOCK_MONOTONIC (cabecera de `/proc/timer_list`) únicamente cuando ambos relojes están disponibles y no cambió el arranque. Si faltan, declara que el tiempo no puede calcularse. Las residencias CPU idle no se presentan como suspensión global. Los contadores se comparan dentro del mismo arranque y período de contabilidad; los datos del kernel desde el arranque pueden preceder a la prueba.

Doze y suspensión del kernel son estados distintos. El diagnóstico no fuerza esos estados ni monta debugfs; tampoco reinicia estadísticas ni modifica WhatsApp o servicios. CPU Respuesta conserva su recolector continuo de tres minutos para uso activo; Acción del módulo de memoria sigue siendo pausa/reactivación. Para esta investigación utiliza el módulo de reposo de dos pulsaciones.

## Revisión de código

Los parches 0017 y 0018 no añaden temporizadores ni wakelocks. La protección de caché puede modificar el equilibrio de reclaim/swap bajo presión; no se descarta un efecto indirecto sin medir. El módulo CPU aplica una vez y termina; solo acorta la espera WALT si registró un cambio válido. El módulo de memoria puede mantener watermark=64. No hay evidencia para responsabilizar a LSPosed u otro módulo concreto.

Se validaron casos de prueba con Android simulado: clocks y reinicio, interfaces ausentes, filtros de datos, escritura/lectura fallidas, almacenamiento bloqueado, captura repetida, symlinks y concurrencia. El primer informe real confirma la coherencia entre relojes y SuspendInfo; no certifica todos los dispositivos ni identifica por sí solo una causa raíz.

Referencias primarias:

- [Reloj monotónico de timer_list en las fuentes de entrega](../kernel-source/linux/kernel/time/timer_list.c).
- [Proyección de pantalla en Android 13](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-13.0.0_r75/services/core/java/com/android/server/media/projection/MediaProjectionManagerService.java).
- [Cambios de memoria rc5](research-rc5-memory.md).
