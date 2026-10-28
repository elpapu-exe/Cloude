# ChatGPT Kernel — reconstrucción 0.1.0-rc3-rebuild1

Kernel experimental para **Redmi Note 12 4G TAPAS/topaz**, con la LineageOS 20 Android 13 del usuario. La ROM y los módulos personales se conservan. Protecciones térmicas, Full LTO, CFI, Shadow Call Stack, BTF y MODVERSIONS siguen siendo requisitos de compilación.

Esta es una **nueva reconstrucción** desde el commit publicado `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86` y los cambios descritos en el resumen del desarrollo anterior. No se recuperaron el commit local rc2, los cambios sin commit rc3 ni sus binarios. Los hashes históricos de rc3 no identifican esta reconstrucción.

**Compilado y publicado mediante GitHub Actions.** [Descargar ZIP instalable — 25,2 MB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058/ChatGPTKernel-0.1.0-rc3-rebuild1-topaz-tapas-A13-KSU.zip) · [SHA256SUMS](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058/SHA256SUMS) · [Publicación y todos sus archivos](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058). El repositorio es privado: usa la cuenta de GitHub con acceso.

**Experimental: esta reconstrucción todavía no se ha probado en el teléfono.** Compilar y conservar los CRC no certifica arranque, estabilidad ni mejora de fluidez. Antes de instalar, guarda un boot verificado fuera del teléfono y lee la [guía de recuperación](docs/installation.md).

El run [40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058) aprobó ARM64, Full LTO/O2, configuración real embebida, inicializador ELF de watermark=64, los 15.543 exports/CRC idénticos a R10, 50 pruebas sin omisiones y el archivo final de fuentes. Se descargaron y verificaron por SHA256 los 34 archivos listados y el propio listado antes de publicar los 35 assets. Conserva CFI, Shadow Call Stack, BTF, MODVERSIONS y térmicas. Hay tres avisos BTF documentados: `filp_close`, `should_failslab` y `vfs_getattr`.

SHA256 del ZIP: `4ecb0febfb9a284c3b624bab7e404ccc205941c69bf3a275312407d1267c2d55`.

[Fuentes correspondientes — archivo auditado](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058/ChatGPTKernel-0.1.0-rc3-rebuild1-sources.tar.zst) · [Resultados de CI](docs/ci-build-result.json) · [Medición y límites del runner](docs/ci-object-measurement.md). El kernel se construyó desde `a01d67ebe63f98a705c068ea735f9ae87848b35c`; cambios posteriores de documentación no cambian ese binario.

[Compilaciones de Actions](https://github.com/elpapu-exe/Cloude/actions) · [Publicaciones](https://github.com/elpapu-exe/Cloude/releases) · [Instalación y recuperación](docs/installation.md) · [Comparación de cinco minutos](docs/testing.md)

La entrega nueva está en la publicación enlazada arriba. `downloads/` conserva el **binario histórico rc1** y sus metadatos; no se deben confundir con la reconstrucción. El recolector canónico actual está en `downloads/chatgpt-kernel-logs.sh`.

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
