# ChatGPT Reposo Diagnóstico 0.1.0-rc2

Módulo de diagnóstico para KernelSU/ReSukiSU, preparado para el Redmi Note 12 4G TAPAS/topaz con Android 13. Ayuda a observar si el teléfono entra en reposo y qué datos de suspensión o consumo están disponibles. No garantiza identificar por sí solo la causa del calentamiento o de la descarga de batería.

rc2 amplía las instantáneas con actividad de procesos y, cuando se pueden leer, datos de alarmas, wakelocks y UID, además del estado de red. Esto permite relacionar las señales del kernel con actividad del sistema y sus aplicaciones. Un contador o nombre aislado no demuestra la causa del consumo; una lectura no disponible queda indicada como limitación.

Instala el ZIP terminado en `KSU.zip` desde KernelSU → Módulos. Si no aparece el botón **Acción**, reinicia una vez y vuelve al módulo. No instala ningún programa que se ejecute durante ese arranque.

1. Desconecta el cargador y pulsa **Acción** para iniciar la captura. Espera a que termine esa pulsación.
2. Apaga la pantalla y deja el teléfono quieto unos diez minutos, conservando WhatsApp y tus módulos.
3. Enciende la pantalla y pulsa **Acción** otra vez para finalizar. Comparte el TXT de `/sdcard/Download` que indique el recolector.

El comando toma dos instantáneas y termina por completo entre pulsaciones. No usa servicio, daemon, temporizador ni wakelock. No cambia zRAM, CPU/GPU, protecciones térmicas, suspensión, SELinux ni otros ajustes. Los únicos archivos propios son el estado privado de la captura en `/data/adb/chatgpt-reposo-diagnostico` y el informe de Descargas. No transmite datos.

Los informes pueden contener nombres de procesos y paquetes, UID, alarmas, wakelocks y datos de estado de red o de uso del teléfono: revísalos antes de compartirlos. Una función o contador no disponible debe aparecer como limitación del diagnóstico; no equivale a ausencia de actividad.

La instalación conserva también `INSTRUCCIONES.txt`; algunas versiones de KernelSU eliminan este README del módulo instalado. El script dentro de `bin/collect.sh` se copia, al construir el ZIP, directamente desde `scripts/chatgpt-suspend-logs.sh`. Las fuentes y las pruebas correspondientes se entregan por separado junto con SHA256SUMS y el manifest de construcción. Las pruebas del host no sustituyen una validación del diagnóstico en el dispositivo.
