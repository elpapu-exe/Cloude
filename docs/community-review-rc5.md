# Candidata rc5: rendimiento de memoria y evaluación pendiente

Estado: **fuentes en preparación; no hay ZIP rc5 publicado**. Los informes ya identifican rc4 en el teléfono. La causa de la percepción de empeoramiento sigue sin demostrarse. La entrega anterior [rc4](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783) conserva sus hashes, fuentes y resultados. Sus auditorías no se transfieren a esta candidata.

## Cambios seleccionados

| Parche | Problema presente | Referencia primaria |
| --- | --- | --- |
| 0017 | MGLRU podía dar muy poco tiempo a la caché no mapeada reutilizada para demostrar su valor. Se ajustan colocación, protección por referencias saturadas y restauración de referencias al refault. | [081488051d28](https://github.com/torvalds/linux/commit/081488051d28d32569ebb7c7a23572778b2e7d57) |
| 0018 | El filtro CMA podía generar recorridos prolongados en el LRU clásico y promociones que no resuelven la recuperación en MGLRU. Se revierte ese filtro conservando restricciones de zona y aislamiento. | [bfe0857c20c6](https://github.com/torvalds/linux/commit/bfe0857c20c663fcc1592fa4e3a61ca12b07dac9) |

Son adaptaciones a las APIs `struct page` existentes, sin cambiar estructuras ni firmas exportadas. Se conservan los vendor hooks. Los detalles, pruebas y riesgos están en [la revisión de memoria](research-rc5-memory.md). Los resultados upstream corresponden a otros escenarios: no son una medición de TikTok o de este TAPAS. En particular, el recorrido extremo reportado para CMA en upstream correspondía al LRU clásico; nuestro MGLRU ya limita cada lote de escaneo.

El recolector v6 añade driver y tasas reales del gobernador, módulos sin direcciones, datos GPU, cpusets/uclamp, CMA, actividad de kswapd y colas de almacenamiento. Solo lee; no instala perfiles ni modifica ajustes. Una captura v5 ya en curso sigue siendo útil y no debe repetirse solo por esta ampliación.

## Ajustes que dependen de los registros

El único ajuste numérico de memoria modificado entre rc3-rebuild1 y rc4 fue el inicializador `watermark_scale_factor`, de 64 a 10. La ROM puede sobrescribirlo. La candidata mantiene 10 mientras no haya evidencia para cambiarlo; no se atribuye una regresión al inicializador sin conocer el valor runtime y los deltas de presión/reclaim. [La documentación del kernel](https://kernel.org/doc/html/v5.15/admin-guide/sysctl/vm.html) relaciona ese margen con ráfagas de asignación y direct reclaim, no con una mejora universal.

La elección de swappiness o del readahead de swap depende del coste relativo de compresión, refaults y almacenamiento. No se fuerzan 3 GiB de zRAM, otro compresor, un TTL MGLRU ni nuevas reglas de LMKD. En Android la política de memoria depende también de [lmkd y sus señales de presión](https://source.android.com/docs/core/perf/lmkd); conservar procesos de forma indefinida puede empeorar la latencia con RAM limitada.

## Descartes y pendientes acotados

- CPU: rc4 no cambió el hot path de schedutil/iowait/uclamp. La captura posterior selecciona WALT, que puede cargarse desde vendor aunque esté desactivado en la configuración del Image GKI. Los drivers Qualcomm y KGSL usados por el teléfono pueden ser módulos vendor externos; cambiar una implementación in-tree deshabilitada no aporta rendimiento. El candidato de límites CPUfreq [7491cdf46b5c](https://github.com/torvalds/linux/commit/7491cdf46b5cbdf123fc84fbe0a07e9e3d7b7620) requiere conjuntamente [b79028039f44](https://github.com/torvalds/linux/commit/b79028039f440e7d2c4df6ab243060c4e3803e84), cuya aplicación literal altera un export. No se incorpora sin una adaptación separada que preserve ABI y una razón medida.
- I/O: dos candidatos F2FS están documentados en [la revisión de almacenamiento](research-rc5-io.md). Se espera conocer el filesystem y la presión de I/O antes de ampliar el alcance. Cambiar el scheduler UFS no acelera directamente la descompresión de zRAM en CPU/RAM.
- MGLRU-FG y la serie moderna de swappiness cambian contratos de contadores y promoción. No se importan como un conjunto de tweaks para probar suerte.
- Las advertencias sobre PSI y swapcache del dossier de memoria son candidatos separados de contabilidad o integridad, no mejoras de FPS demostradas.

Se conservan ROM, módulos necesarios, WhatsApp, protecciones térmicas, CFI, Full LTO/O2, SCS, BTF y MODVERSIONS. Antes de publicar siguen siendo obligatorias la compilación ARM64 completa, igualdad de exports/CRC con R10, IKCONFIG real, auditoría del archivo final de fuentes y descarga verificada de todos los assets. La evaluación en hardware requerirá comparar registros y uso semejante antes y después.

## Comprobaciones locales

Pasaron 93 pruebas obligatorias sin omisiones sobre `.cache/linux`. La reaplicación de los 18 parches produjo los 40 archivos finales esperados; los árboles preparados Linux/KSU/BBG coinciden con el snapshot en contenido, tipos y destinos literales de enlaces. La configuración difiere de rc4 solo en LOCALVERSION; la compilación completa y la comparación de ABI del binario nuevo siguen pendientes.

La compilación incremental ARM64 de objetos (`descend -j2`) terminó sin errores en 45 segundos; recompiló los archivos afectados y reutilizó los demás objetos. No ejecutó Image/Full LTO ni valida un ZIP. [Medición y hashes](ci-object-measurement-rc5.json). Se mantiene el último marcador automático de compilación en rc4: rc5 todavía no se ha solicitado a Actions.

Una segunda observación sí incluye varias horas del mismo arranque, con presión de memoria y un cambio de zRAM de 2 a 3 GiB, además de límites CPU distintos. Confirma que el margen se aplicó y se retiró, pero no constituye una comparación controlada de su efecto. La identificación del controlador de zRAM es necesaria para evitar superponer perfiles; no se considera este archivo una repetición equivocada de la captura inicial.
