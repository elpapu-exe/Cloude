# ChatGPT Kernel — rc5 publicada

**Reposo recuperado al apagar Bluetooth:** el usuario confirmó ese único cambio y que no tenía accesorios conectados. Se midió 92,5% del intervalo suspendido, batería 40 → 38 °C y UART inactiva. Se investiga el módulo vendor y su cliente para conservar Bluetooth utilizable. [Resultado](docs/suspend-result-uart-released.md) · [Siguiente fase](docs/bluetooth-uart-investigation.md).

Kernel experimental para **Redmi Note 12 4G TAPAS/topaz y Android 13**. Conserva la ROM, los módulos necesarios, KernelSU/ReSukiSU y las protecciones térmicas. La LineageOS 20 del usuario es la referencia; otras ROM A13 requieren comprobación real.

**[Descargar rc5 — 25,2 MB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc5-9c81476ba0a6-41290063824/ChatGPTKernel-0.1.0-rc5-topaz-tapas-A13-KSU.zip)** · [SHA256SUMS](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-kernel-0.1.0-rc5-9c81476ba0a6-41290063824/SHA256SUMS) · [Entrega, fuentes y logs](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc5-9c81476ba0a6-41290063824)

SHA256 del ZIP: `0d419065b704c276e12055a0ddb0d1a4126893d898b2fa0032f07b161dfaa4cc`.

[Actions 41290063824](https://github.com/elpapu-exe/Cloude/actions/runs/41290063824) completó la compilación ARM64 con Full LTO/O2, CFI, Shadow Call Stack, BTF y MODVERSIONS. Pasaron **93 pruebas sin omisiones**, los **15.543 exports/CRC** coincidieron con R10 y se auditaron las **77.010 entradas del archivo final de fuentes**. Los 35 assets se descargaron y verificaron antes de publicar. **Una captura del teléfono identifica rc5 arrancada; la mejora de fluidez o ANR sigue sin medirse y se investiga reposo/temperatura.** [Evidencia](docs/ci-build-result-rc5.json).

[Instalación, respaldo y recuperación](docs/installation.md) · [Prueba breve](docs/testing.md) · [Compilación en Actions](docs/build.md) · [Revisión de los cambios](docs/community-review-rc5.md)

## Cambios de rc5 respecto a rc4

- MGLRU: proteger mejor la caché reutilizada, conservar referencias saturadas y restaurar el estado apropiado al volver a cargar páginas expulsadas.
- Reclaim: retirar el filtro CMA que podía prolongar recorridos en LRU clásico y provocar promociones improductivas en MGLRU. Se conservan las restricciones de zona y aislamiento.
- Recolector v6: identificar drivers/tasas reales de CPU, GPU, almacenamiento, CMA y presión de memoria. Los resultados upstream pertenecen a otros escenarios; no son una medición de este TAPAS.

La configuración efectiva difiere de rc4 solo en LOCALVERSION. Se mantienen MGLRU activo y `watermark_scale_factor=10` como inicializador, modificable por la ROM. Se conservan las correcciones anteriores de KProfiles, Horizon, SSG, Binder y F2FS. El gobernador observado en el teléfono es WALT cargado desde vendor; las correcciones de Horizon actúan al seleccionar Horizon.

## Módulo CPU y captura de tres minutos

**[Descargar ChatGPT CPU Respuesta — 25 KB](https://github.com/elpapu-exe/Cloude/releases/download/chatgpt-cpu-respuesta-0.1.0-rc1-7b0a51d49a6b-41291184310/ChatGPT-CPU-Respuesta-0.1.0-rc1-KSU.zip)** · [Instrucciones](modules/chatgpt-cpu-respuesta/INSTRUCCIONES.txt) · [Hashes y fuentes](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-cpu-respuesta-0.1.0-rc1-7b0a51d49a6b-41291184310) · [Evidencia](docs/cpu-respuesta-release.json).

Durante la investigación de reposo, si ya lo instalaste, desactiva CPU Respuesta y reinicia conservando los demás módulos necesarios. Su comportamiento experimental es el siguiente: reduce un 25% la espera WALT `up_rate_limit_us` únicamente cuando su valor está entre 20001 y 100000 µs y los controles se identifican sin ambigüedad. Es una elección experimental; con tasas habituales de 500/1000/2000 µs no cambia nada. Se aplica una vez al arrancar y conserva cambios posteriores de otros controladores. No supone una CPU un 25% más rápida.

**Acción recoge 180 segundos de logs** con el recolector v7 sin alternar el perfil. Usa TikTok y cambia entre tus apps, conservando WhatsApp y módulos. Comparte el TXT de Descargas cuando aparezca `TEST FINISHED`. Pasaron 33 pruebas y se verificaron los cinco assets. Falta medir el efecto real.

GPU, frecuencias/límites, voltajes, térmicas, zRAM y LMKD conservan su gestión habitual. [SmartPack y persistencia de los 3 GiB](docs/smartpack.md). Para la primera comparación del kernel conserva los mismos ajustes; el módulo CPU es una prueba independiente.

## Entregas anteriores y procedencia

- [rc4](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783): identificada arrancada en los informes; no hay comparación controlada de rendimiento. [Resultado propio](docs/ci-build-result-rc4.json).
- [rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058): reconstrucción nueva; el binario rc3 histórico no se recuperó. [Resultado propio](docs/ci-build-result.json).
- [Módulo Fluidez Memoria](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-fluidez-0.1.0-rc1-717b18174da0-41151064733): independiente, sin cambios. Su Acción pausa/reactiva y guarda snapshots; difiere de Acción del módulo CPU. [Instrucciones](modules/chatgpt-fluidez-memoria/INSTRUCCIONES.txt).

rc5 corresponde al commit `9c81476ba0a6ffc452d5fdb5463cf5cebf128ad9`. Sus assets mantienen los documentos del snapshot previo a publicar; esta documentación posterior registra la entrega sin reemplazar sus binarios. El recolector v7 y las 33 pruebas del módulo CPU pertenecen a su ejecución independiente.

Base Linux 5.15.216 / Zepharo R10 `d246c8c17548bb1a2756092cabf34d11eedcde8c`, ReSukiSU histórico `7e92d45e` (35142), BBG `a54e0dc6` y candidato SUSFS 2.3.0 `7af04b08`. La procedencia exacta del SUSFS de R10 sigue sin demostrarse. Las fuentes grandes se distribuyen como assets, fuera del historial Git normal.

**Repositorio privado:** inicia sesión con la cuenta de GitHub que tiene acceso para descargar.
