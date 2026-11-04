# ChatGPT Reposo Diagnóstico 0.1.0-rc3

Módulo de diagnóstico para KernelSU/ReSukiSU, preparado para el Redmi Note 12 4G TAPAS/topaz con Android 13. Ayuda a observar si el teléfono entra en reposo y qué datos de suspensión o consumo están disponibles. No garantiza identificar por sí solo la causa del calentamiento o de la descarga de batería.

rc3 añade lecturas del enlace UART, estado de gestión de energía, parámetros del módulo Bluetooth y posibles procesos asociados, cuando el sistema permite acceder a esos datos. Conserva las lecturas de actividad de procesos, alarmas, wakelocks, UID y estado de red. Una coincidencia, un nombre o un contador aislado no demuestra qué componente causa el consumo; una lectura no disponible queda indicada como limitación.

Actualiza el ZIP terminado en `KSU.zip` desde KernelSU → Módulos. Reinicia si el gestor lo requiere para aplicar la actualización; si no aparece **Acción**, reinicia una vez y vuelve al módulo. No instala ningún programa que se ejecute durante ese arranque.

Para esta fase, deja desactivados los perfiles experimentales ChatGPT de CPU y memoria. Conserva Wi-Fi, WhatsApp y los módulos que necesitas.

1. Desconecta el cargador. Activa Bluetooth **sin conectar accesorios** y espera un minuto.
2. Pulsa **Acción** para iniciar la captura. Espera a que termine esa pulsación.
3. Desactiva Bluetooth, espera unos diez segundos y pulsa **Acción** otra vez para finalizar de inmediato. Comparte el TXT de `/sdcard/Download` que indique el recolector.

Esta prueba compara estados de Bluetooth y UART. Para esta fase no hace falta esperar diez minutos ni apagar la pantalla.

El comando toma dos instantáneas y termina por completo entre pulsaciones. No usa servicio, daemon, temporizador ni wakelock. No cambia zRAM, CPU/GPU, protecciones térmicas, suspensión, SELinux ni otros ajustes. Los únicos archivos propios son el estado privado de la captura en `/data/adb/chatgpt-reposo-diagnostico` y el informe de Descargas. No transmite datos.

Los informes pueden contener nombres de procesos y paquetes, UID, alarmas, wakelocks y datos de estado de red o de uso del teléfono: revísalos antes de compartirlos. Una función o contador no disponible debe aparecer como limitación del diagnóstico; no equivale a ausencia de actividad.

La instalación conserva también `INSTRUCCIONES.txt`; algunas versiones de KernelSU eliminan este README del módulo instalado. El script dentro de `bin/collect.sh` se copia, al construir el ZIP, directamente desde `scripts/chatgpt-suspend-logs.sh`. Las fuentes y las pruebas correspondientes se entregan por separado junto con SHA256SUMS y el manifest de construcción. Las pruebas del host no sustituyen una validación del diagnóstico en el dispositivo.
