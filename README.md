# ChatGPT Kernel — reconstrucción 0.1.0-rc3-rebuild1

Kernel experimental para **Redmi Note 12 4G TAPAS/topaz**, con la LineageOS 20 Android 13 del usuario. La ROM y los módulos personales se conservan. Protecciones térmicas, Full LTO, CFI, Shadow Call Stack, BTF y MODVERSIONS siguen siendo requisitos de compilación.

Esta es una **nueva reconstrucción** desde el commit publicado `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86` y los cambios descritos en el resumen del desarrollo anterior. No se recuperaron el commit local rc2, los cambios sin commit rc3 ni sus binarios. Los hashes históricos de rc3 no identifican esta reconstrucción.

**Estado:** fuentes reconstruidas y pruebas de regresión locales; compilación ARM64 y entrega pendientes de GitHub Actions. No se afirma arranque, estabilidad ni mejora medida en el teléfono. La percepción favorable comunicada por el usuario corresponde a una versión anterior.

[Compilaciones de Actions](https://github.com/elpapu-exe/Cloude/actions) · [Publicaciones](https://github.com/elpapu-exe/Cloude/releases) · [Instalación y recuperación](docs/installation.md) · [Comparación de cinco minutos](docs/testing.md)

No hay un enlace directo nuevo hasta que Actions compile, audite, publique y compruebe la descarga. `downloads/` conserva el **binario histórico rc1** y sus metadatos; no se deben confundir con la reconstrucción. El recolector canónico actual está en `downloads/chatgpt-kernel-logs.sh`.

## Cambios de la candidata

- MGLRU existente activo por defecto; configuración real embebida y arreglos de KProfiles retenidos de rc1.
- `watermark_scale_factor=64` como inicializador experimental de margen de recuperación. La ROM o los módulos pueden sobrescribirlo tras arrancar; no garantiza fluidez.
- Horizon: tablas dinámicas protegidas, entrada sysfs estricta, caché invalidada ante rechazos y actualización de límites coherente. **Schedutil sigue siendo el gobernador predeterminado.**
- MGLRU: conservar el tipo anon/file observado en el CAS exitoso al actualizar contabilidad batched.
- SSG: lectura de política dentro de RCU, errores de entrada sysfs y capacidad real de metadatos por petición. No se consideran resueltos todos sus problemas históricos.

No hay cambios nuevos de tamaño/compresor zRAM, LMKD, swappiness, frecuencias, voltajes ni límites térmicos. No se atribuye una fuga concreta o los ANR del teléfono a un único componente sin registros.

## Fuentes y entrega

Base Linux 5.15.216 / Zepharo R10 `d246c8c17548bb1a2756092cabf34d11eedcde8c`, ReSukiSU histórico `7e92d45e` (35142), BBG `a54e0dc6` y candidato SUSFS 2.3.0 `7af04b08`. La procedencia exacta del SUSFS de R10 sigue sin demostrarse. Pines completos en `config/sources.lock.json`; límites y referencias en [revisión](docs/community-review-rc3.md).

Actions conserva ZIP, configuración efectiva, SHA256SUMS, registros, comparación ABI y fuentes correspondientes comprimidas, sin añadir el archivo grande a Git. La publicación exige comprobar el archivo final de fuentes y volver a descargar todos los assets para verificar sus hashes. [Receta y recursos](docs/build.md).
