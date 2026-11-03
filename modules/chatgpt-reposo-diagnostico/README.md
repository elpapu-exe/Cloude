# ChatGPT Reposo Diagnóstico 0.1.0-rc1

Módulo de diagnóstico para KernelSU/ReSukiSU, preparado para el Redmi Note 12 4G TAPAS/topaz con Android 13. Ayuda a observar si el teléfono entra en reposo y qué datos de suspensión o consumo están disponibles. No garantiza identificar por sí solo la causa del calentamiento o de la descarga de batería.

Instala el ZIP terminado en `KSU.zip` desde KernelSU → Módulos. Si no aparece el botón **Acción**, reinicia una vez y vuelve al módulo. No instala ningún programa que se ejecute durante ese arranque.

1. Desconecta el cargador y pulsa **Acción** para iniciar la captura. Espera a que termine esa pulsación.
2. Apaga la pantalla y deja el teléfono quieto unos diez minutos, conservando WhatsApp y tus módulos.
3. Enciende la pantalla y pulsa **Acción** otra vez para finalizar. Comparte el TXT de `/sdcard/Download` que indique el recolector.

El comando toma dos instantáneas y termina por completo entre pulsaciones. No usa servicio, daemon, temporizador ni wakelock. No cambia zRAM, CPU/GPU, protecciones térmicas, suspensión, SELinux ni otros ajustes. Los únicos archivos propios son el estado privado de la captura en `/data/adb/chatgpt-reposo-diagnostico` y el informe de Descargas. No transmite datos.

Los informes pueden contener datos de uso del teléfono: revísalos antes de compartirlos. Una función o contador no disponible debe aparecer como limitación del diagnóstico; no equivale a ausencia de actividad.

La instalación conserva también `INSTRUCCIONES.txt`; algunas versiones de KernelSU eliminan este README del módulo instalado. El script dentro de `bin/collect.sh` se copia, al construir el ZIP, directamente desde `scripts/chatgpt-suspend-logs.sh`. Las fuentes y las pruebas correspondientes se entregan por separado junto con SHA256SUMS y el manifest de construcción. Las pruebas del host no sustituyen una validación del diagnóstico en el dispositivo.
