# ChatGPT Kernel — rc5 en preparación; rc4 publicada

**Módulo KernelSU publicado:** [Descargar ChatGPT Fluidez Memoria — 16 KB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-fluidez-0.1.0-rc1-717b18174da0-41151064733/ChatGPT-Fluidez-Memoria-0.1.0-rc1-KSU.zip) · [SHA256SUMS](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-fluidez-0.1.0-rc1-717b18174da0-41151064733/SHA256SUMS) · [Instrucciones](modules/chatgpt-fluidez-memoria/INSTRUCCIONES.txt). Instala desde KernelSU y reinicia. Acción pausa/restaura o reactiva y guarda un informe. Conserva tus módulos y las protecciones térmicas; no requiere flashear otro kernel. Pasaron 23 pruebas y se verificó la descarga de sus cinco assets; todavía no hay mejora medida en el teléfono. [Evidencia](docs/fluidez-module-release.json). El repositorio es privado: inicia sesión con la cuenta que tiene acceso.

**Módulo CPU en preparación:** [ChatGPT CPU Respuesta](modules/chatgpt-cpu-respuesta/README.md), un piloto WALT condicionado al valor real de su tasa. Acción recoge tres minutos de CPU/GPU/memoria sin cambiar el perfil. Sus fuentes y 33 pruebas están listas; todavía no hay enlace de descarga publicado.

**Estado de desarrollo:** rc5 añade dos correcciones de rendimiento de memoria y el recolector v6. Todavía no hay ZIP rc5 publicado; los enlaces de descarga siguientes corresponden a rc4. [Revisión y evaluación pendiente](docs/community-review-rc5.md).

Kernel experimental para **Redmi Note 12 4G TAPAS/topaz y Android 13**. Conserva la ROM, los módulos necesarios y las protecciones térmicas. La LineageOS 20 del usuario sigue siendo la referencia de uso; la compatibilidad con otras ROM A13 requiere comprobación real.

**rc4 compilada, auditada y publicada.** [Descargar ZIP — 25,2 MB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783/ChatGPTKernel-0.1.0-rc4-topaz-tapas-A13-KSU.zip) · [SHA256SUMS](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783/SHA256SUMS) · [Entrega y fuentes](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783). El repositorio es privado: usa la cuenta de GitHub con acceso.

SHA256 del ZIP: `069f0fa1b59b39767597f40f78988f3a5aeaef70df468b2a8bc825c412f42265`. [Actions 40663572783](https://github.com/elpapu-exe/Cloude/actions/runs/40663572783) completó 71 pruebas sin omisiones, comparación de los 15.543 exports/CRC con R10 y auditoría de las 76.992 entradas del archivo final de fuentes. Los 35 assets se descargaron y verificaron antes de publicar. **Un informe del teléfono ya identifica rc4 arrancada; estabilidad prolongada y rendimiento siguen sin validación.** [Resultado completo](docs/ci-build-result-rc4.json).

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

rc4 se compiló desde `0640e8f41412eba3b66ce3b353735897dc322842`; los cambios posteriores de documentación no cambian ese binario. Los avisos BTF efectivos son `filp_close`, `should_failslab` y `vfs_getattr`. `downloads/` conserva el binario histórico rc1 y sus metadatos; el recolector actual está en `downloads/chatgpt-kernel-logs.sh`.

Base Linux 5.15.216 / Zepharo R10 `d246c8c17548bb1a2756092cabf34d11eedcde8c`, ReSukiSU histórico `7e92d45e` (35142), BBG `a54e0dc6` y candidato SUSFS 2.3.0 `7af04b08`. La procedencia exacta del SUSFS de R10 sigue sin demostrarse. Los pines están en `config/sources.lock.json`; las fuentes correspondientes grandes se distribuyen como assets y no se añaden al historial Git normal.
