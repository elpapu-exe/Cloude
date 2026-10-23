# ChatGPT Kernel

Kernel personalizado para Redmi Note 12 4G (topaz/tapas), basado en el Zepharo R10 que ya funciona con la LineageOS 20 no oficial del usuario.

**Estado: 0.1.0-rc1 compilado y verificado estáticamente; todavía sin prueba de arranque ni rendimiento en el teléfono.** Los 15.543 exports y sus CRC coinciden con R10. La compilación no sustituye una prueba real de arranque, llamadas, cámara, Wi-Fi, carga y suspensión. Véanse [estado](STATUS.md) y [notas de versión](docs/release-notes.md), incluidos tres avisos BTF conocidos.

## Objetivo

Reducir trabajo innecesario y mejorar la gestión de memoria de un equipo de 4 GB, conservando la ROM, los módulos del vendor, KernelSU, WaEnhancer e InstaEclipse. Se mantendrán las protecciones térmicas y la verificación de compatibilidad de módulos. No se promete eliminar toda la lentitud ni aumentar la RAM física.

## Base fijada

- Fuentes: `belowzeroiq/kernel_msm-5.15`, commit `d246c8c17548bb1a2756092cabf34d11eedcde8c`.
- Referencia funcional: `5.15.216-Zepharo-R10-gd246c8c17548`.
- Configuración y dependencias fijadas en `config/`; la configuración IKCONFIG extraída de la imagen publicada corresponde a un archivo stock y no se tomará como receta efectiva.
- Instalación prevista: AnyKernel3 conservando el resto del arranque y sin sustituir DTB, DTBO ni módulos del vendor.

## Trabajo

La investigación de memoria y la matriz de alternativas están en `docs/`. Esta primera entrega compila una candidata sobre las fuentes R10 fijadas; no realiza una segunda compilación completa de referencia ni afirma reproducir el binario del mantenedor.

Los cambios propios son MGLRU activo por defecto (el usuario confirmó `0x0000` en R10), correcciones de bloqueo/contexto en KProfiles y la incorporación de la configuración real en IKCONFIG. No se aumentan frecuencias, voltajes ni límites térmicos. Se mantienen los mecanismos KSU/SUSFS y Baseband Guard de la base.

Consulta [compilación](docs/build.md), [instalación y recuperación](docs/installation.md) y [compatibilidad](docs/compatibility-review.md). No existe una garantía de eliminar toda la lentitud con 4 GB de RAM.

Los directorios `.cache`, `out`, `logs` y `dist` son locales y se excluyen de Git. Ningún comando de construcción debe flashear el teléfono ni publicar archivos automáticamente.
