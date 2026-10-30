# rc5: revisión de memoria después de rc4

El usuario describe el comportamiento actual como similar o quizá peor, aclara que la percepción es incierta y prepara una captura del recolector. La versión instalada todavía debe confirmarse en ese informe. **No hay todavía registros nuevos que identifiquen la causa ni una mejora de rendimiento medida.** Los cambios de este documento son propuestas implementadas en fuentes para revisión; no sustituyen la evaluación necesaria para elegir otra compilación de Actions o una entrega nueva. La autorización del usuario para continuar el desarrollo y compilar ya existe. La configuración candidata solo cambia LOCALVERSION; no se modifican watermark, compresor/tamaño de zRAM o políticas de LMKD.

## Diferencia de watermark que debe comprobarse en runtime

rc3-rebuild1 compiló `watermark_scale_factor=64`; rc4 lo restauró a 10 mediante 0016. Ambos usan MGLRU activo por defecto. La ROM o un módulo pueden sobrescribir esos valores después del arranque; si ambos kernels terminan con el mismo valor, la diferencia de inicializador no basta para explicar su comportamiento en uso.

En esta base, `__setup_per_zone_wmarks()` calcula por zona:

```
gap = max(min_de_la_zona / 4, managed_pages * watermark_scale_factor / 10000)
low = min + gap
high = min + 2 * gap
```

Por eso pasar de 64 a 10 no equivale a liberar una cantidad fija de RAM ni a multiplicar toda la reserva por 6,4. El primer término puede dominar. Un margen menor puede dejar menos tiempo para reclaim de fondo ante una ráfaga de asignación, pero conservar más memoria para otros usos. Ninguna dirección garantiza más fluidez.

El v5 que el usuario ya está ejecutando recoge el valor real, presión y contadores. No se le pide repetir la captura por esta revisión. Si la hipótesis siguiera abierta, los watermarks de `/proc/zoneinfo` y los contadores de llegada rápida a watermarks permitirían precisar la reserva y la actividad de kswapd. Todavía no se atribuye una regresión a 0016.

## 0017: protección insuficiente de caché reutilizada

Fuente primaria: [081488051d28d32569ebb7c7a23572778b2e7d57, “mm/mglru: fix underprotected page cache”](https://github.com/torvalds/linux/commit/081488051d28d32569ebb7c7a23572778b2e7d57). [Publicación original](https://lore.kernel.org/20231208061407.2125867-1-yuzhao@google.com/).

La base rc4 aún contiene los tres comportamientos anteriores al arreglo: `lru_gen_add_page()` sitúa páginas limpias sin mapeo en la generación más antigua; `sort_page()` solo protege por umbral de tier, incluso con referencias saturadas; y `lru_gen_refault()` no restituye todo el estado de referencias para los casos que deberían haber quedado protegidos. Una generación muy breve puede expulsar caché reutilizada antes de que el controlador responda a los refaults.

La adaptación usa las APIs de páginas ya presentes:

- Coloca páginas ordinarias en la segunda generación más antigua cuando hay suficiente separación; conserva la más antigua para reintento explícito y ventanas cortas.
- Coloca páginas que aún no pueden expulsarse en la segunda generación más joven y conserva la generación más joven para páginas activas.
- Protege referencias saturadas y restituye el contador/estado workingset en los refaults correspondientes.

Se modifican solamente `include/linux/mm_inline.h`, `mm/vmscan.c` y `mm/workingset.c`. Se conservan hooks, estructuras, prototipos y símbolos. No se requieren APIs de folios modernas ni la infraestructura por nodo añadida después a MGLRU. La contabilidad active/inactive sigue usando `lru_gen_is_active()` y `lru_gen_update_size()` existentes.

El autor publicó menos refaults de archivo en una carga Android de lanzamiento de aplicaciones. Eso justifica evaluar este camino activo; no traslada una cifra de mejora a TAPAS, TikTok o esta ROM. El riesgo principal es cambiar el equilibrio de protección entre caché y memoria anónima: retener más caché útil puede cambiar el tráfico de swap y el momento de actuar de LMKD. La comparación debe observar ambos lados, no solo `workingset_refault_file`.

## 0018: retirar el filtrado CMA que upstream revirtió

Fuente primaria: [bfe0857c20c663fcc1592fa4e3a61ca12b07dac9, “Revert mm: skip CMA pages when they are not available”](https://github.com/torvalds/linux/commit/bfe0857c20c663fcc1592fa4e3a61ca12b07dac9). Revierte también [b7108d66318a](https://github.com/torvalds/linux/commit/b7108d66318abf3e060c7839eabcba52e9461568).

rc4 conserva el helper `skip_cma()` y sus llamadas en aislamiento clásico y `sort_page()` de MGLRU, con `CONFIG_CMA=y`. Para reclaim directo no MOVABLE, se saltaban esas páginas aunque eso pudiera prolongar recorridos bajo el lock LRU. Upstream retiró esa optimización tras informes de presión y tiempos de bloqueo elevados.

La adaptación elimina el helper y sus dos llamadas, conservando el filtro por zona, los límites de escaneo y los demás controles de elegibilidad, mapeo e I/O. No altera reservas CMA, configuración, estructuras, interfaces o vendor hooks. Kswapd ya quedaba fuera del filtro retirado; no se cambian sus otros contratos.

El ejemplo extremo de recorridos publicado por upstream corresponde al aislamiento del LRU clásico. Nuestra implementación MGLRU ya limita cada recorrido con `MAX_LRU_BATCH`; no se afirma reproducir esa magnitud de bloqueo aquí. En el camino MGLRU, el cambio evita promover una página únicamente por el motivo CMA retirado. Permitir recuperar CMA puede liberar páginas que no satisfagan directamente una asignación no MOVABLE, de modo que tampoco se presenta como una ganancia universal.

## Pruebas y evidencia que falta

```sh
python3 tests/test_mglru_cache_protection.py
python3 tests/test_mglru_cma.py
CHATGPT_TEST_SOURCE_ROOT=.cache/linux python3 tests/test_mglru_cache_protection.py
CHATGPT_TEST_SOURCE_ROOT=.cache/linux python3 tests/test_mglru_cma.py
```

La suite de caché compila los helpers C reales de inserción, actualización de tamaños, borrado, promoción, ordenación y refault con ASan/UBSan. Sus diez casos comprueban ventanas de dos/tres/cuatro generaciones, páginas compuestas de 512 páginas base, referencias saturadas, filtros por memcg/nodo, hooks y caminos sin protección adicional. Se congelaron los tres helpers anteriores de rc4: seis casos detectan el comportamiento anterior como control negativo. No son un benchmark ni una prueba de concurrencia completa del kernel.

La suite CMA tiene seis pruebas y compara los recorridos reales con sus controles previos. En una lista modelada de 8.192 páginas CMA, el aislamiento clásico y MGLRU toman un lote de 64 después del arreglo. Antes, el camino clásico recorre la banda y MGLRU agota su límite de 4.096 promoviendo páginas, sin aislarlas por ese motivo. Los controles conservan zonas, páginas compuestas, permisos de unmap/writeback, referencias, kswapd y límites para páginas no elegibles por otros motivos. Estos números son propiedades de la fixture, no tiempos medidos en el teléfono. Las pruebas de helpers no sustituyen la compilación ARM64, exports/CRC, ABI o una captura real. Esas comprobaciones deben ejecutarse antes de cualquier entrega seleccionada.

Para interpretar los registros del teléfono:

| Observación correlacionada | Hipótesis que orienta |
| --- | --- |
| Refault de archivo, fallos mayores y presión de I/O aumentan durante cambios de app | Caché expulsada y releída; 0017 es un candidato relevante, sin demostrar causalidad por un contador aislado. |
| Mucho `pswpin/pswpout`, zRAM ocupada y presión de CPU/memoria | Tráfico de memoria anónima y coste de swap/compresión; retener caché adicional puede ayudar o empeorar el equilibrio. |
| Presión sostenida con CMA disponible y mucha actividad de escaneo | Merece revisar 0018; los agregados no identifican cuánto tiempo se mantuvo el lock ni el motivo de cada página descartada. |
| Poca presión de memoria pero límites de CPU/GPU reducidos o temperatura creciente | Investigar primero esa ruta; estos parches MM no se anuncian como solución a límites térmicos o de frecuencia. |

El tamaño lógico de zRAM no es su consumo físico. Hay que distinguir `orig_data_size`, `compr_data_size`, `mem_used_total` y espacio libre de swap. Las protecciones térmicas y los módulos necesarios se conservan. No se añaden pruebas de estrés ni comandos destructivos al teléfono.

## Revisión de MGLRU-FG y descartes

Se leyó [MGLRU-FG v4, 17 parches](https://lore.kernel.org/linux-mm/20261016-mglru-fg-v4-0-2106750c0bfa@tencent.com/) y se contrastó con esta implementación. En su carta, “aligned tree” significa código alineado con upstream; no identifica un arreglo aislado de alineación de cacheline. La serie cambia contadores a atómicos, reglas de promoción y flags, contabilidad, reparenting y recorridos de smaps/GUP/DAMON. Nuestra base conserva contadores ordinarios y campos antiguos por ABI; no es correcto extraer las operaciones lockless sin sus contratos previos. El autor comunicó menos tráfico en sus pruebas, pero sin una diferencia consistente de jank/FPS en el ensayo Pixel citado. La prueba Xperia 1 V con 5.15 no certifica este TAPAS. No se importa la serie ni se transfieren sus cifras.

Otros descartes acotados:

- [5095a2b23987, detener reclaim en watermarks altos](https://github.com/torvalds/linux/commit/5095a2b23987d3c3c47dd16b3d4080e2733b8bb9): repara un safeguard retirado en otra revisión. Esta base conserva `should_abort_scan()` con sus comprobaciones de watermarks; no se considera ausencia equivalente ni se copia el refactor por nodo.
- [b130ba4a6259, reiniciar fallos de kswapd solo si hay progreso](https://github.com/torvalds/linux/commit/b130ba4a6259f6b64d8af15e9e7ab1e912bcb7ad): la ruta común aquí ya usa `if (reclaimable)` antes de reiniciar `kswapd_failures`; no contiene el reinicio incondicional corregido por ese commit.
- [d8c47cc7bf602ef73384a00869a70148146c1191, PSI en swapins fríos](https://github.com/torvalds/linux/commit/d8c47cc7bf602ef73384a00869a70148146c1191): candidato de contabilidad ausente, no incluido en 0017/0018. `swap_readpage()` actualmente entra y sale de PSI sin condicionar esas operaciones a `PageWorkingset(page)`; la lectura síncrona de zRAM mediante `bdev_read_page()` queda dentro de ese intervalo. Upstream captura el estado workingset al entrar y condiciona ambos extremos a la misma captura. La detección de workingset anónimo y la retirada de su marcado incondicional ya existen en `swap_state.c`/`memory.c`. No acelera la descompresión ni reduce trabajo de memoria por sí mismo; puede cambiar la señal observada y las decisiones de LMKD. Exige pruebas de páginas frías/calientes, errores y cambios del flag durante la operación, manteniendo enter/leave emparejados. PSI y swapin agregados no separan por sí solos trabajo frío de refault caliente, por lo que no se rebaja la presión observada ni se atribuye el problema a un error de medición sin evidencia.
- [13ddaf26be32, carrera al omitir swapcache](https://github.com/torvalds/linux/commit/13ddaf26be324a7f951891ecd9ccd04466d27458): cuestión de estabilidad separada, con adaptación de varias salidas y archivos. Debe revisarse junto a [01626a182302](https://github.com/torvalds/linux/commit/01626a18230246efdcea322aa8f067e60ffe5ccd), que corrige esperas de un tick introducidas por el primer arreglo. Esas esperas no están actualmente en nuestras fuentes; no se les atribuyen los tirones presentes.
- [7ef28e8b8142, liberar zspages fuera de class lock](https://github.com/torvalds/linux/commit/7ef28e8b81426375ddec0f1c1459767cc9b2df2c): su port necesita revisar migración, aislamiento y liberación diferida distintos en 5.15. No se importa un fragmento aislado.
- Los cambios modernos de recompresión/writeback de zRAM no corresponden a la configuración y frontend presentes. No se encontró un fallo primario demostrado de LZ4KD que justifique cambiar el compresor. Se mantienen los arreglos de contabilidad y seguridad ya incluidos, sin presentarlos como ganancias nuevas de rendimiento.

Checkpatch no detecta errores de código en 0017/0018. Conserva avisos de metadatos por commits upstream ausentes en la historia local y un `Reported-by` original sin `Closes` (regla posterior a la publicación de ese arreglo). Se mantienen los trailers publicados; no se inventan informes o firmas para eliminar esos avisos.
