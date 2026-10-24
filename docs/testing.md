# Prueba breve y un solo archivo de diagnóstico

La versión 0.1.0-rc1 está compilada, comprobada estáticamente y tiene una primera prueba de arranque y uso registrada en un teléfono. Eso no valida todas sus funciones ni la estabilidad a largo plazo. Mantén disponible R10 KSU y una copia recuperable del boot, como explica [instalación y recuperación](installation.md).

## Uso

1. Instala el kernel desde un recovery compatible y reinicia. Antes de la prueba de rendimiento comprueba que funcionan root, llamadas, Wi-Fi y cámara. Si hay problemas básicos o reinicios, vuelve a R10.
2. Descarga `chatgpt-kernel-logs.sh` en **Descargas** del teléfono.
3. En Termux pega una sola vez:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-kernel-logs.sh'
```

Acepta el permiso de KernelSU si aparece. El comando muestra la ruta de un archivo `ChatGPTKernel-<fecha>-<id>.txt`. Si no encuentra el script, revisa que el navegador no haya cambiado su nombre o la carpeta de descarga.

4. Usa TikTok y alterna con tus apps habituales durante unos diez minutos. Mantén los módulos que necesitas y las protecciones térmicas activas. Haz esta primera prueba desenchufado, para distinguir la carga del uso normal. Conserva Termux en recientes; no lo fuerces a cerrar.
5. Al cabo de 10–12 minutos, adjunta **solo ese `.txt`** desde Descargas al chat. El marcador `TEST FINISHED` al final confirma que terminó. Si Android mata el recolector, el archivo parcial todavía puede servir; si el teléfono se suspende, el tiempo real puede alargarse.

No se necesitan capturas ni comandos adicionales. El informe incluye la identidad del kernel ejecutado, por lo que también sirve como referencia si se ejecuta sobre R10 antes de instalar.

## Qué recoge

- Una muestra cada diez segundos: RAM, swap, PSI de memoria/CPU/I/O, contadores de recuperación y paginación, zRAM, uso global de CPU, frecuencias y temperaturas disponibles.
- Configuración de MGLRU/zRAM y propiedades concretas de kernel/ROM; versión instalada de TikTok.
- Procesos con mayor RSS/CPU, usando nombres y sin argumentos; la cifra CPU de `ps` puede ser un promedio desde que arrancó el proceso.
- PSS/swap de TikTok al terminar, eventos LMKD y de ANR/muerte de procesos, resumen de ANR de TikTok y un extracto acotado de sus pilas si existe una traza reciente.
- Errores concretos del kernel desde el arranque. Las trazas pueden incluir TikTok como proceso secundario y se etiquetan así; su mera presencia no demuestra que sufriera el ANR.

## Captura de fluidez de dos minutos

Para tirones sin ANR, descarga [chatgpt-fluidez.sh](../downloads/chatgpt-fluidez.sh) en Descargas y ejecuta:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-fluidez.sh 120'
```

Es el recolector general v4 con un nombre de descarga distinto para evitar ejecutar por error una copia antigua. Usa las apps normalmente durante unos dos minutos, con el teléfono desenchufado, y comparte el único `ChatGPTKernel-<fecha>-<id>.txt` cuando aparezca `TEST FINISHED`. Las consultas y la suspensión pueden alargar el tiempo. No necesita provocar un bloqueo, reiniciar, limpiar datos ni modificar ajustes.

Esta versión añade uso de CPU por núcleo, máximos de hardware/política, parámetros WALT y KProfiles disponibles, preferencias de refresco y contadores HWUI al inicio/final de TikTok y SystemUI. Las preferencias de pantalla no prueban el refresco real. Los títulos de ventanas y las jerarquías de vistas quedan excluidos; solo se guardan resúmenes y filas numéricas de fotogramas.

Los contadores gráficos solo pueden compararse si coinciden PID y `Stats since`. Sus percentiles son acumulados; no se restan para calcular el intervalo. El anillo de fotogramas cubre solo actividad reciente, puede repetir registros entre capturas y no representa necesariamente el vídeo de TikTok, que puede usar una superficie distinta. No usar un umbral fijo de 16,67 ms para todos los modos ni convertir estos datos automáticamente a FPS de pantalla. El muestreo de recursos cada diez segundos permite detectar presión sostenida, pero no demuestra por sí solo la causa de cada microtirón.

La versión 4 incluye los dispositivos zRAM adicionales y los valores concretos disponibles de LMKD, junto con versiones de Instagram/InstaEclipse. Para el ensayo temporal de capacidad adicional, consulta [la guía específica](zram-trial.md); el recolector por sí mismo sigue siendo de solo lectura.

Los archivos sysfs y proc solo se leen. El recolector escribe el informe y su directorio temporal de control; no modifica ajustes, detiene apps, limpia cachés/logs ni sube datos. No instala un servicio de arranque.

El `.txt` contiene nombres de apps y datos de diagnóstico; puedes revisarlo antes de compartirlo. Se excluyen líneas de comando completas, mensajes generales de excepciones de otras apps y las secciones de bases de datos de `meminfo`. La batería y las zonas CPU/SoC son sensores distintos; las frecuencias leídas pueden ser solicitadas en lugar de medidas. Las muestras no equivalen a una medición de FPS ni certifican estabilidad.

## Captura puntual de SecureElement y TikTok

Si el informe muestra cierres repetidos de `com.android.se` con motivo `bg anr`, usa [chatgpt-secureelement-logs.sh](../downloads/chatgpt-secureelement-logs.sh). Descárgalo en Descargas y ejecuta:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-secureelement-logs.sh'
```

Termina en primer plano, normalmente en pocos segundos, y muestra la ruta de un único `ChatGPTKernel-SE-<fecha>-<id>.txt`. Comparte ese archivo. No hay que repetir la prueba de diez minutos ni reiniciar.

La versión 2 consulta el último resumen ANR si corresponde a SecureElement o TikTok, el bloque SecureElement en las tres trazas ANR más recientes y un bloque de TikTok entre las últimas 32 trazas. Busca primero una traza cuyo proceso principal sea TikTok; si solo lo encuentra como secundario, lo indica expresamente. Así puede recuperar un fallo que haya dejado de ser el ANR más reciente, siempre que su traza todavía exista.

También consulta servicios/HAL de SecureElement y el estado actual de batería, límites de CPU y refrigeración. Informa de los comandos que fallan o agotan su tiempo. El estado térmico recogido después no reconstruye el estado exacto del momento del ANR. No modifica ajustes ni detiene servicios. `com.android.se` gestiona elementos seguros eSE/UICC/SIM y no debe desactivarse suponiendo que únicamente sirve para NFC.

Si las pilas confirman una espera de eSE ausente mientras SIM1/SIM2 están registrados, existe un [parche experimental específico para tapas con Android 13](../modules/chatgpt-se-fix/README.md). Se instala como APK de LSPosed, con ámbito exclusivo `com.android.se`; necesita validación en el teléfono y no sustituye el diagnóstico de memoria o temperatura.

## Validación del recolector

Se comprobó la sintaxis con BusyBox ash y se ejecutó con archivos y comandos Android simulados. Las pruebas verifican muestras, terminación, ausencia de cambios a los archivos de sistema simulados y exclusión de otro proceso en ANR. El recolector general ya completó una captura real en esta ROM; el puntual de SecureElement todavía necesita esa primera ejecución real.
