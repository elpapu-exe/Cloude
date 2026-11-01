# Estado y continuación

Entrega anterior: **0.1.0-rc4, compilada y publicada mediante GitHub Actions**.

Candidata en preparación: **0.1.0-rc5**. Se adaptan 0017/0018 de protección de caché MGLRU y retirada del filtro CMA. El primer informe identifica rc4, pero solo observa unos 15 segundos del primer minuto de arranque. Falta una captura de uso estable para escoger ajustes. Pasaron 93 regresiones sin omisiones, la recompilación ARM64 incremental de objetos y el replay exacto de 18 parches. No hay compilación completa ni enlace de descarga rc5. [Preparación verificable](docs/rc5-preparation.json). [Revisión](docs/community-review-rc5.md).

## Trabajo de rc4

Se añaden seis correcciones comprobadas como ausentes: dos de MGLRU (contador de escaneo y VMA especiales), una de cuota Binder, una de serialización al iniciar schedutil/Horizon y dos de manejo de rangos/errores F2FS. La [revisión internacional](docs/community-review-rc4.md) enlaza los commits primarios, la adaptación y los descartes. El parche 0016 restaura `watermark_scale_factor=10`, retirando el experimento 64 para una candidata de alcance TAPAS/A13 general.

Las pruebas locales nuevas compilan funciones C reales con ASan/UBSan y controles negativos: memoria/Binder, arranque de los gobernadores y rangos F2FS. Son modelos de regresión del host. Su [ejecución propia](https://github.com/elpapu-exe/Cloude/actions/runs/40663572783) terminó con build y publicación SUCCESS: 71 pruebas sin fallos ni omisiones; 15.543 exports/CRC idénticos a R10; IKCONFIG real, inicializador ELF watermark=10 y archivo final de fuentes auditado. La descarga verificó dos veces los 34 archivos de SHA256SUMS, antes y después de subirlos, y publicó 35 assets. [Resultado rc4](docs/ci-build-result-rc4.json).

[Entrega rc4](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783), commit compilado `0640e8f41412eba3b66ce3b353735897dc322842`. ZIP: 25.216.352 bytes; SHA256 `069f0fa1b59b39767597f40f78988f3a5aeaef70df468b2a8bc825c412f42265`. Fuentes tar.zst: 195.371.053 bytes; SHA256 `4438ea9297310b93e2021930e3165edc51a758a42b0cd2489a9fee64f5c855fb`. Avisos BTF: `filp_close`, `should_failslab`, `vfs_getattr`.

Se mantienen la ROM y los módulos necesarios, root histórico, MGLRU activo, CFI, Full LTO/O2, SCS, BTF, MODVERSIONS y térmicas. No se introducen cambios de zRAM, LMKD, swappiness, frecuencias o voltajes. La restauración del watermark afecta su inicializador compilado; la ROM conserva la posibilidad de sobrescribirlo.

## Entrega anterior verificada

[rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) se construyó desde `a01d67ebe63f98a705c068ea735f9ae87848b35c` en [Actions 40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058). Sus 15.543 exports/CRC coincidieron con R10, pasaron 50 pruebas sin omisiones y se auditó el tar final. Se descargaron y comprobaron los 34 archivos del listado SHA256SUMS y el propio listado antes de publicar sus 35 assets.

ZIP anterior: 25.215.885 bytes; SHA256 `4ecb0febfb9a284c3b624bab7e404ccc205941c69bf3a275312407d1267c2d55`. Los avisos BTF de esa compilación fueron `filp_close`, `should_failslab` y `vfs_getattr`. Más detalles en [ci-build-result.json](docs/ci-build-result.json). Esos datos describen la versión anterior, cuyo inicializador watermark era 64.

La receta de Actions ya completó esa entrega en un runner estándar con limpieza limitada al entorno desechable, checkout parcial y swap automática. Las mediciones de [objetos y recursos](docs/ci-object-measurement.md) justifican sus límites para esta carga; rc4 debe comprobar de nuevo la capacidad real. No se requiere compilar en Windows ni configurar un runner personal para repetir la receta existente.

## Recuperación del trabajo previo

Este checkout comenzó limpio en el commit publicado `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. La rama remota disponible era `chatgpt-kernel-download`; `main` no existía. El commit local rc2 `b6107b63…`, rc3 sin commit y sus binarios históricos no se recuperaron. No se borró ni sobrescribió el entorno anterior y no se declara perdido su disco por no poder acceder a él.

rc3-rebuild1 fue una reconstrucción nueva a partir de rc1 y del resumen registrado. Sus fuentes originales se adquirieron mediante Git real o archivos codeload con SHA256 y recibos honestos. KSU requiere historia original completa para conservar la identidad 35142; no se fabrica un historial Git.

## Pendiente

El informe identifica rc4 arrancada. Faltan funciones básicas, estabilidad prolongada, root/módulos, notificaciones de WhatsApp y una captura de uso estable con el recolector. rc3-rebuild1 sigue sin una prueba de arranque confirmada. La experiencia favorable histórica corresponde a una versión anterior.

## Módulo de memoria

Se publicó ChatGPT Fluidez Memoria0.1.0-rc1 para KernelSU/ReSukiSU, TAPAS/topaz Android13 y kernel5.15 ARM64. Tiene dos ajustes experimentales: activar el coreMGLRU cuando estaba desactivado y elevar watermark hasta64 si era menor. El primer informe confirma el cambio y la restauración del valor de control, pero su intervalo de arranque no demuestra causa ni mejora. Conserva ROM, módulos, térmicas y seguridad. Pasaron 23 pruebas de scripts reales con fixtures Android, incluidas restauración, cambios de terceros, reinicio/actualización, escrituras fallidas, máscara inválida y pausa persistente; no sustituyen rendimiento en hardware. Su workflow y publicación son independientes del kernel y no solicitan una compilación rc5.

[Entrega del módulo](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-fluidez-0.1.0-rc1-717b18174da0-41151064733), [Actions41151064733](https://github.com/elpapu-exe/Cloude/actions/runs/41151064733), commit `717b18174da04859413c8936ce2f193d10e82593`. Los jobs build/publish terminaron SUCCESS, pasaron23pruebas sin omisiones y el publicador descargó los5assets y comprobó los4archivos de SHA256SUMS dos veces (8OK). ZIP instalable:16.236bytes; SHA256 `90832f5a97d9090004fd49c6565be969b4a36ca70f1e47385c2cb9ef675d03c3`. [Manifest de evidencia](docs/fluidez-module-release.json). La mejora real en el dispositivo sigue sin medirse. La fuente rc5 y su compilación de kernel completa continúan pendientes del informe; esta entrega no ha solicitado otro build del kernel.

## Primera observación del teléfono

La captura se identifica como rc4, con MGLRU activo antes del módulo y WALT seleccionado en ambas políticas. Solo abarca aproximadamente 15 segundos del primer minuto de arranque; el margen pasó de 1 a 64 y volvió a 1 tras unos nueve segundos. Hay presión y tráfico de memoria, pero no una comparación estable del perfil. La capacidad lógica de zRAM es 2 GiB y su consumo físico es una magnitud distinta. La batería no basta para diagnosticar limitación térmica de CPU/SoC. No se publicó el archivo original ni identificadores de arranque. El siguiente paso es una captura de 180 segundos después de estabilizar el arranque, conservando módulos/WhatsApp y sin más cambios. Se corrigió el descarte de WALT basado únicamente en la configuración GKI; su receta vendor y el gobernador observado contradicen esa inferencia.
