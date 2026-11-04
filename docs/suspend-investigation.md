# Investigación de reposo con rc5

**Quinto informe: mejora medida.** UART permanece inactivo, el sistema suspende 898,70 s de 971,25 s (92,5%) y la batería pasa de 40 a 38 °C. El periodo contable se conserva. [Resultado y límites](suspend-result-uart-released.md). El usuario confirmó que el único cambio fue apagar Bluetooth, antes encendido sin accesorios. La asociación Bluetooth/UART es fuerte; falta identificar el driver/HAL y el mecanismo concreto. [Fase actual y captura breve rc3](bluetooth-uart-investigation.md).

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

## Captura actual: Bluetooth/UART con rc3

**[Descargar ZIP rc3 — 19,2 KB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-reposo-diagnostico-0.1.0-rc3-8c6010416a2e-41903620910/ChatGPT-Reposo-Diagnostico-0.1.0-rc3-KSU.zip)** · [Hashes y fuentes](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-reposo-diagnostico-0.1.0-rc3-8c6010416a2e-41903620910) · [Evidencia rc3](reposo-module-release-rc3.json). Publicado por Actions después de 31 pruebas sin omisiones y de descargar y verificar sus cinco assets. Las fuentes también ejecutaron las 31 pruebas de forma independiente. Es el mismo módulo de diagnóstico actualizado; no cambia ajustes ni instala otro kernel.

1. Actualiza Reposo Diagnóstico desde KernelSU/ReSukiSU y reinicia si lo pide el gestor. Mantén desactivados los perfiles experimentales ChatGPT de CPU y memoria; conserva WhatsApp, la red y tus módulos personales.
2. Desconecta cargador/USB, enciende Bluetooth **sin conectar accesorios** y espera un minuto.
3. Pulsa **Acción**, espera **START SAVED** y a que termine esa pulsación.
4. Apaga Bluetooth, espera diez segundos y pulsa **Acción** otra vez. Comparte el TXT de Descargas indicado por **TEST FINISHED**.

Esta captura compara los estados de Bluetooth, UART, runtime PM, módulo vendor y clientes. **No requiere diez minutos ni apagar la pantalla; su porcentaje de reposo no evalúa una mejora.** [Investigación y límites de los nuevos lectores](bluetooth-uart-investigation.md).

El recolector termina por completo entre pulsaciones. No usa servicio, temporizador ni wakelock, no modifica ajustes ni transmite datos. Conserva las lecturas de procesos, alarmas, UID, red, presión de memoria y suspensión. Las nuevas filas BLE excluyen nombres/direcciones de accesorios, filtros y UUID; el dump bruto no se guarda. Puede contener nombres de apps, procesos y datos de uso: revisa el TXT antes de compartirlo. [Instrucciones incluidas](../modules/chatgpt-reposo-diagnostico/INSTRUCCIONES.txt).

La suspensión aproximada se calcula por diferencia de CLOCK_BOOTTIME y CLOCK_MONOTONIC únicamente dentro del mismo arranque y cuando ambos relojes están disponibles. Los contadores de batería requieren el mismo periodo contable. Una lectura no disponible no demuestra ausencia de actividad; una fila de escáner BLE o un descriptor abierto tampoco demuestra qué retiene un voto UART. No se abren dispositivos UART ni se fuerzan estados de energía.

## Revisión de código

Los parches 0017 y 0018 no añaden temporizadores ni wakelocks. La protección de caché puede modificar el equilibrio de reclaim/swap bajo presión; no se descarta un efecto indirecto sin medir. El módulo CPU aplica una vez y termina; solo acorta la espera WALT si registró un cambio válido. El módulo de memoria puede mantener watermark=64. No hay evidencia para responsabilizar a LSPosed u otro módulo concreto.

Se validaron casos de prueba con Android simulado: clocks y reinicio, interfaces ausentes, filtros de datos, escritura/lectura fallidas, almacenamiento bloqueado, captura repetida, symlinks y concurrencia. El primer informe real confirma la coherencia entre relojes y SuspendInfo; no certifica todos los dispositivos ni identifica por sí solo una causa raíz.

Referencias primarias:

- [Reloj monotónico de timer_list en las fuentes de entrega](../kernel-source/linux/kernel/time/timer_list.c).
- [Proyección de pantalla en Android 13](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-13.0.0_r75/services/core/java/com/android/server/media/projection/MediaProjectionManagerService.java).
- [Cambios de memoria rc5](research-rc5-memory.md).
