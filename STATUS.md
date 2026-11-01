# Estado y continuación

**0.1.0-rc5 compilada, auditada y publicada** por [Actions 41290063824](https://github.com/elpapu-exe/Cloude/actions/runs/41290063824), desde `9c81476ba0a6ffc452d5fdb5463cf5cebf128ad9`. [Entrega](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc5-9c81476ba0a6-41290063824) · [Evidencia completa](docs/ci-build-result-rc5.json).

ZIP: 25,216,619 bytes; SHA256 `0d419065b704c276e12055a0ddb0d1a4126893d898b2fa0032f07b161dfaa4cc`. Fuentes tar.zst: 195,383,642 bytes; SHA256 `3559b47d1fea259ce63cd408ff3b1981a79d2d4957521ad485f8d68eb864403a`. Se conservan como assets, fuera del historial Git normal.

## Validación de rc5

- ARM64 completo, Full LTO/O2, CFI, SCS, BTF, MODVERSIONS y protecciones térmicas conservados.
- 93 pruebas obligatorias, sin fallos ni omisiones, sobre el árbol compilado; replay previo de 18 parches sobre 40 archivos finales.
- 15.543 exports y CRC idénticos a R10; ningún símbolo añadido, ausente o cambiado. Esto no prueba los módulos concretos del teléfono.
- IKCONFIG idéntica a la configuración efectiva e inicializador ELF watermark=10.
- Archivo final de fuentes: 77.010 entradas verificadas por contenido, tipo, modo y destinos literales de enlaces.
- 35 assets descargados y verificados antes de publicar: 34 hashes comprobados dos veces, más comparación del propio SHA256SUMS.

Runner observado: dos CPU, aproximadamente 7,75 GiB RAM, 28 GiB de swap adicional. Full LTO/Image: 52 min 15 s con paginación considerable. El éxito corresponde a esta configuración medida. Avisos BTF: filp_close, should_failslab, vfs_getattr.

La configuración difiere de rc4 solo en LOCALVERSION. Los cambios nuevos protegen caché reutilizada en MGLRU y retiran el filtro CMA problemático en reclaim. [Revisión](docs/community-review-rc5.md). No se modifican zRAM, LMKD, swappiness, frecuencias o voltajes.

## Módulo CPU publicado

ChatGPT CPU Respuesta 0.1.0-rc1: [entrega](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-cpu-respuesta-0.1.0-rc1-7b0a51d49a6b-41291184310) · [evidencia](docs/cpu-respuesta-release.json). ZIP 24,960 bytes; SHA256 `0a0070959d330c901860a876305640c9c099a53e6fda2d9135fb007fe4e07a90`. Sus 33 pruebas y cinco assets fueron verificados en una ejecución independiente. Solo ajusta condicionalmente WALT up_rate_limit_us; Acción recoge 180 segundos con el recolector v7. El kernel rc5 congelado contiene v6 y 93 pruebas. No se modificó el módulo de memoria.

## Observaciones y siguiente prueba

Los informes identifican rc4, MGLRU activo y WALT seleccionado desde vendor. El primero dura unos 15 segundos al arrancar. El segundo contiene unas 4 h 22 min del mismo arranque con presión de memoria/IO, cambios de zRAM de 2 a 3 GiB y límites CPU diferentes. No permite atribuir una mejora o regresión a un parámetro concreto. El usuario identifica SmartPack como gestor de zRAM; [persistencia](docs/smartpack.md). Los informes originales y sus identificadores no se publicaron.

**Pendiente en el teléfono:** arranque y funciones básicas de rc5, root/módulos, WhatsApp, estabilidad, fluidez y temperatura. Una captura de tres minutos con Acción del módulo CPU mantiene el perfil actual, WhatsApp y los módulos necesarios. El módulo es opcional; para comparar kernels mantén los mismos ajustes. [Procedimiento](docs/testing.md).

## Historia conservada

[rc4](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783) y [rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) conservan resultados propios. El [módulo de memoria](docs/fluidez-module-release.json) mantiene su versión y estado independiente.

Este checkout comenzó desde el remoto 4fc1ad554ac54ffce0a6792ca6d85f67435e8a86, rama chatgpt-kernel-download; main no existía. El commit rc2 local y rc3 sin publicar no se recuperaron. El entorno anterior no se borró ni sobrescribió. rc3-rebuild1 fue una reconstrucción nueva. KSU utiliza su historia original completa para conservar 35142; no se fabricó un historial Git.

Los documentos dentro de los assets son el snapshot del commit compilado. La actualización posterior de documentación conserva los binarios auditados y no solicita otra compilación.
