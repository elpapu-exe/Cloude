# Prueba breve y un solo archivo de diagnóstico

La versión 0.1.0-rc1 está compilada y comprobada estáticamente, pero aún necesita prueba de arranque y uso en el teléfono. Mantén disponible R10 KSU y una copia recuperable del boot, como explica [instalación y recuperación](installation.md).

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

Los archivos sysfs y proc solo se leen. El recolector escribe el informe y su directorio temporal de control; no modifica ajustes, detiene apps, limpia cachés/logs ni sube datos. No instala un servicio de arranque.

El `.txt` contiene nombres de apps y datos de diagnóstico; puedes revisarlo antes de compartirlo. Se excluyen líneas de comando completas y mensajes generales de excepciones de otras apps. La batería y las zonas CPU/SoC son sensores distintos; las frecuencias leídas pueden ser solicitadas en lugar de medidas. Las muestras no equivalen a una medición de FPS ni certifican estabilidad.

## Validación del recolector

Se comprobó su sintaxis con BusyBox ash y se ejecutó con archivos y comandos Android simulados. Las pruebas verifican muestras, terminación, ausencia de cambios a los archivos de sistema simulados y exclusión de otro proceso en ANR. Su primera ejecución real en esta ROM todavía debe verificarse.
