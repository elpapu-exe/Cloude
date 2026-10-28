# Comparación breve: un archivo por kernel

La candidata [**0.1.0-rc4**](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783) está compilada y publicada con hashes verificados. Recoge la referencia del kernel actual antes de instalarla y repite después la prueba. [rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) es la entrega anterior publicada, con sus propias fuentes y hashes. Ninguna de esas dos candidatas tiene una prueba de arranque confirmada en este teléfono. La percepción favorable histórica de una versión anterior no demuestra que rc4 arranque, elimine ANR o mejore la fluidez.

Antes de instalar, guarda fuera del teléfono la copia verificada de `boot` y lee [instalación y recuperación](installation.md). Tras instalar comprueba root, llamadas, Wi-Fi y cámara antes de medir rendimiento. Si hay reinicios o fallos básicos, restaura el arranque anterior.

## Prueba de cinco minutos

Haz una captura con el kernel que utilizas ahora, antes de cambiarlo. Repite una sola vez después de instalar y reiniciar la candidata, dejando pasar el mismo tiempo desde el arranque y esperando a que el teléfono recupere una temperatura inicial parecida.

1. Conserva tu ROM, TikTok oficial, WhatsApp y los módulos necesarios: Integrity Box, Hybrid Mount, ReVanced, Leica, LSPosed/NeoZygisk, WaEnhancer e InstaEclipse según tu instalación actual. Mantén activas las protecciones térmicas y WhatsApp con sus notificaciones habituales. No cambies opciones de batería, gobernador, zRAM ni ajustes entre las dos capturas.
2. Descarga el recolector actualizado [chatgpt-kernel-logs.sh](../downloads/chatgpt-kernel-logs.sh) en **Descargas**. Ejecuta una vez en Termux y acepta root de KernelSU si aparece:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-kernel-logs.sh 300'
```

3. Con el teléfono desenchufado, usa TikTok normal unos tres minutos. Durante los dos minutos restantes, alterna varias veces entre TikTok, WhatsApp y las mismas dos apps que acostumbras usar. Usa un brillo, refresco, conexión y secuencia parecidos en ambas capturas. Conserva Termux en recientes.
4. Espera el marcador `TEST FINISHED` al final del `.txt` indicado. La recogida final añade algunos segundos; si Android mata el recolector, conserva el archivo parcial. Comparte el `.txt` de cada kernel y una frase: tirones percibidos, ANR si apareció y si WhatsApp notificó de inmediato. No hace falta una captura de pantalla ni otra tanda de comandos.

Si solo puedes entregar un archivo, envía primero la referencia del kernel actual. No hace falta provocar un bloqueo. Una notificación de WhatsApp que recibas normalmente durante la prueba sirve como comprobación práctica; el informe por sí solo no mide su latencia de entrega.

## Qué permite comparar

El informe guarda identidad del kernel/ROM, versión de TikTok, MGLRU y parámetros de memoria realmente activos, no solo sus valores compilados. Cada diez segundos recoge RAM disponible, swap, PSI, contadores de reclaim/paginación, zRAM, CPU, frecuencias y sensores disponibles. Registra el filesystem montado en `/data` para distinguir F2FS de ext4. También recoge resúmenes de procesos, memoria de TikTok, eventos LMKD/ANR y contadores gráficos al inicio y al final. La versión 5 consulta HWUI para las dos variantes oficiales de TikTok (`com.zhiliaoapp.musically` y `com.ss.android.ugc.trill`) y SystemUI.

Se compararán presión de memoria sostenida y deltas de contadores durante intervalos semejantes, incidencias de ANR/muerte de procesos y evolución térmica. El tamaño lógico de zRAM no equivale a RAM física consumida: `orig_data_size`, `compr_data_size` y `mem_used_total` son cifras distintas. Un valor de `watermark_scale_factor` cambiado por la ROM después del arranque puede diferir del inicializador del kernel. rc4 restaura el inicializador de la base a 10; rc3-rebuild1 usaba 64. Anota el valor realmente observado en cada informe: esa diferencia forma parte de la comparación y no demuestra por sí sola la causa de un cambio de fluidez.

Los contadores gráficos solo se pueden comparar dentro de una captura si coinciden PID y `Stats since`. Los percentiles son acumulados y no deben restarse. El anillo de fotogramas representa actividad HWUI reciente; el vídeo de TikTok puede utilizar otra superficie. No equivale a FPS de pantalla ni justifica un umbral fijo de 16,67 ms para cualquier refresco. El muestreo de diez segundos detecta presión sostenida, pero no identifica la causa de cada microtirón.

La temperatura de batería y las zonas CPU/SoC son sensores distintos. Los valores crudos y su unidad se etiquetan en el informe; un sensor ausente no significa temperatura cero. Una prueba corta orienta el siguiente cambio y no certifica estabilidad prolongada, batería ni superioridad de rendimiento.

## Alcance del recolector

El script solo lee ajustes y registros. Escribe su informe y un directorio temporal de control; no ajusta zRAM/LMKD, detiene apps, limpia cachés/logs, desactiva servicios ni instala nada al arranque. No transmite datos. Conserva los módulos y las protecciones térmicas. No requiere Hail ni otro TikTok. No uses los ensayos temporales antiguos de zRAM para esta comparación.

El `.txt` puede contener nombres de apps y trazas de diagnóstico; puedes revisarlo antes de compartirlo. Se excluyen argumentos completos de procesos, bases de datos de `meminfo`, títulos de ventanas y jerarquías de vistas. El ANR más reciente puede preceder a la prueba y una aparición de TikTok como proceso secundario no demuestra que fuera la aplicación bloqueada. La ausencia de una traza accesible tampoco demuestra ausencia de ANR.

La sintaxis y las pruebas con archivos/comandos Android simulados comprueban muestras, terminación, filtrado y conservación de los archivos de sistema simulados. Esta revisión del recolector necesita su primera captura real. Si un informe ya existente requiere más contexto, están disponibles el [estado puntual de memoria](../downloads/chatgpt-memory-status.sh) y el [diagnóstico SecureElement](../downloads/chatgpt-secureelement-logs.sh); no son pasos obligatorios de esta comparación.
