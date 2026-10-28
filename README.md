# ChatGPT Kernel 0.1.0-rc4 — candidata pendiente de CI

Kernel experimental para **Redmi Note 12 4G TAPAS/topaz y Android 13**. Conserva la ROM, los módulos necesarios y las protecciones térmicas. La LineageOS 20 del usuario sigue siendo la referencia de uso; la compatibilidad con otras ROM A13 requiere comprobación real.

**rc4 todavía no tiene ZIP publicado ni validación de arranque o rendimiento.** La candidata incorpora seis correcciones concretas revisadas contra estas fuentes y retira el ajuste experimental de margen de memoria. Sus pruebas locales no sustituyen una compilación ARM64 completa ni los registros del teléfono.

[Revisión internacional y decisiones](docs/community-review-rc4.md) · [Compilación en Actions](docs/build.md) · [Instalación y recuperación](docs/installation.md) · [Comparación de cinco minutos](docs/testing.md)

## Cambios de rc4 respecto a rc3-rebuild1

- MGLRU: evitar el desbordamiento del contador de escaneo al reintentar páginas y omitir VMA especiales en el recorrido vecino de PTE.
- Binder: completar la comprobación de cuota asíncrona para no rechazar una petición que sí cabe en el espacio restante.
- CPUfreq: serializar el inicio de schedutil y Horizon con las escrituras de sus límites de tasa. **Schedutil sigue por defecto.**
- F2FS: propagar el error del segundo writeback de `collapse_range` y comprobar solapamiento después de expandir una longitud cero en `MOVE_RANGE`. Solo actúan en los caminos afectados de F2FS.

El parche 0016 restaura el inicializador **`watermark_scale_factor=10`**, valor de la base, en lugar del 64 experimental de rc3-rebuild1. No se había medido una ventaja general de 64 para TAPAS/A13. La ROM puede modificar el valor tras arrancar; volver a 10 tampoco garantiza mayor fluidez.

Se conservan MGLRU activo, la configuración real embebida, los arreglos anteriores de KProfiles/Horizon/SSG y las integraciones históricas de root. No se cambian tamaño o compresor de zRAM, LMKD, swappiness, frecuencias, voltajes o límites térmicos. CFI, Full LTO/O2, Shadow Call Stack, BTF y MODVERSIONS siguen siendo obligatorios. No se atribuyen los ANR a una causa concreta sin evidencia del dispositivo.

## Entrega anterior disponible

La versión **0.1.0-rc3-rebuild1** ya fue compilada y publicada por [Actions 40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058). Es la versión anterior, no el binario rc3 histórico que quedó inaccesible:

[ZIP anterior — 25,2 MB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058/ChatGPTKernel-0.1.0-rc3-rebuild1-topaz-tapas-A13-KSU.zip) · [SHA256SUMS anterior](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058/SHA256SUMS) · [Publicación y fuentes](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) · [Evidencia de esa compilación](docs/ci-build-result.json)

SHA256 del ZIP anterior: `4ecb0febfb9a284c3b624bab7e404ccc205941c69bf3a275312407d1267c2d55`. El repositorio es privado: utiliza la cuenta de GitHub que tiene acceso. Esta entrega anterior tampoco tiene una prueba de arranque confirmada en el teléfono del usuario; sus validaciones no se transfieren a rc4.

La publicación de rc4 solo se enlazará después de compilar, comprobar imagen/configuración/ABI, auditar las fuentes finales y verificar la descarga de sus assets. `downloads/` conserva el binario histórico rc1 y sus metadatos; el recolector actual está en `downloads/chatgpt-kernel-logs.sh`.

Base Linux 5.15.216 / Zepharo R10 `d246c8c17548bb1a2756092cabf34d11eedcde8c`, ReSukiSU histórico `7e92d45e` (35142), BBG `a54e0dc6` y candidato SUSFS 2.3.0 `7af04b08`. La procedencia exacta del SUSFS de R10 sigue sin demostrarse. Los pines están en `config/sources.lock.json`; las fuentes correspondientes grandes se distribuyen como assets y no se añaden al historial Git normal.
