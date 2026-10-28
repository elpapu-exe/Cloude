# Estado y continuación

Candidata actual: **0.1.0-rc4, pendiente de compilación completa y publicación en GitHub Actions**.

## Trabajo de rc4

Se añaden seis correcciones comprobadas como ausentes: dos de MGLRU (contador de escaneo y VMA especiales), una de cuota Binder, una de serialización al iniciar schedutil/Horizon y dos de manejo de rangos/errores F2FS. La [revisión internacional](docs/community-review-rc4.md) enlaza los commits primarios, la adaptación y los descartes. El parche 0016 restaura `watermark_scale_factor=10`, retirando el experimento 64 para una candidata de alcance TAPAS/A13 general.

Las pruebas locales nuevas compilan funciones C reales con ASan/UBSan y controles negativos: memoria/Binder, arranque de los gobernadores y rangos F2FS. Son modelos de regresión del host. La compilación ARM64, exports/CRC, configuración embebida, BTF, imagen, archivo final de fuentes y descarga de rc4 deben pasar en su propia ejecución. No se considera completado ese trabajo por los resultados de rc3-rebuild1.

Se mantienen la ROM y los módulos necesarios, root histórico, MGLRU activo, CFI, Full LTO/O2, SCS, BTF, MODVERSIONS y térmicas. No se introducen cambios de zRAM, LMKD, swappiness, frecuencias o voltajes. La restauración del watermark afecta su inicializador compilado; la ROM conserva la posibilidad de sobrescribirlo.

## Entrega anterior verificada

[rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) se construyó desde `a01d67ebe63f98a705c068ea735f9ae87848b35c` en [Actions 40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058). Sus 15.543 exports/CRC coincidieron con R10, pasaron 50 pruebas sin omisiones y se auditó el tar final. Se descargaron y comprobaron los 34 archivos del listado SHA256SUMS y el propio listado antes de publicar sus 35 assets.

ZIP anterior: 25.215.885 bytes; SHA256 `4ecb0febfb9a284c3b624bab7e404ccc205941c69bf3a275312407d1267c2d55`. Los avisos BTF de esa compilación fueron `filp_close`, `should_failslab` y `vfs_getattr`. Más detalles en [ci-build-result.json](docs/ci-build-result.json). Esos datos describen la versión anterior, cuyo inicializador watermark era 64.

La receta de Actions ya completó esa entrega en un runner estándar con limpieza limitada al entorno desechable, checkout parcial y swap automática. Las mediciones de [objetos y recursos](docs/ci-object-measurement.md) justifican sus límites para esta carga; rc4 debe comprobar de nuevo la capacidad real. No se requiere compilar en Windows ni configurar un runner personal para repetir la receta existente.

## Recuperación del trabajo previo

Este checkout comenzó limpio en el commit publicado `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. La rama remota disponible era `chatgpt-kernel-download`; `main` no existía. El commit local rc2 `b6107b63…`, rc3 sin commit y sus binarios históricos no se recuperaron. No se borró ni sobrescribió el entorno anterior y no se declara perdido su disco por no poder acceder a él.

rc3-rebuild1 fue una reconstrucción nueva a partir de rc1 y del resumen registrado. Sus fuentes originales se adquirieron mediante Git real o archivos codeload con SHA256 y recibos honestos. KSU requiere historia original completa para conservar la identidad 35142; no se fabrica un historial Git.

## Pendiente

Terminar las comprobaciones globales y CI de rc4, publicar sus artefactos y verificar sus descargas. Después comprobar arranque, funciones básicas, root/módulos, notificaciones de WhatsApp y la [prueba de cinco minutos](docs/testing.md). Ni rc4 ni rc3-rebuild1 tienen una prueba de arranque confirmada en este teléfono. La experiencia favorable histórica corresponde a una versión anterior.
