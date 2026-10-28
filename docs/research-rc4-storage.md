# rc4: correcciones acotadas de F2FS y revisión de SSG

La revisión de almacenamiento para la candidata rc4 identifica dos fallos concretos de integridad/manejo de errores en F2FS. Ambos están presentes en la base R10 Linux 5.15.216 de este proyecto y tienen backports oficiales para la rama 5.15. Las correcciones no modifican la configuración, los límites térmicos, el planificador I/O elegido ni sus constantes.

**No hay mediciones nuevas de fluidez, ANR, temperatura o batería en el teléfono.** `CONFIG_F2FS_FS=y` está confirmado en la configuración efectiva; no se conoce el tipo de filesystem montado en `/data` del usuario. Estos cambios solo actúan cuando se utilizan los caminos afectados de F2FS. Si userdata usa ext4, no cambian sus operaciones habituales sobre ese volumen.

## Parche 0014: propagar el error de writeback de collapse_range

`f2fs_collapse_range()` comprueba el writeback inicial, mueve los bloques y vuelve a escribir las páginas movidas. La base ignora el resultado de este segundo writeback. Aunque este falle, continúa truncando page cache/bloques, puede actualizar el tamaño y devolver éxito.

El parche captura el segundo resultado y sale por el desbloqueo existente cuando hay un error. Evita el truncado posterior y la actualización de tamaño en ese camino; no afirma deshacer el movimiento ya realizado antes del fallo.

Fuentes primarias:

- Upstream: [f8a4108800254d6f7b2755515fbbd9d0caac561e](https://github.com/torvalds/linux/commit/f8a4108800254d6f7b2755515fbbd9d0caac561e), incorporado el 3 de agosto de 2026.
- Backport 5.15 utilizado: [4adebfe52db633992b35cc183e2520cf0c2b56bf](https://github.com/gregkh/linux/commit/4adebfe52db633992b35cc183e2520cf0c2b56bf), incorporado el 14 de septiembre de 2026.
- Archivo de parche: [0014-f2fs-propagate-collapse-writeback-errors.patch](../patches/0014-f2fs-propagate-collapse-writeback-errors.patch).

El archivo conserva la autoría, fecha y trailers publicados de la corrección estable. No se añade una firma DCO en nombre de este proyecto. Su fecha de autoría puede preceder a la fecha de incorporación indicada arriba.

## Parche 0015: comprobar solapamiento con la longitud efectiva

`F2FS_IOC_MOVE_RANGE` interpreta `len == 0` como mover desde el origen hasta EOF. La comprobación de solapamiento dentro del mismo inode se hacía antes de esa expansión. En un archivo de cuatro bloques, mover desde el bloque 0 al bloque 1 con longitud cero superaba la comprobación y terminaba intercambiando rangos solapados: el caso de corrupción que debía rechazarse.

El parche mantiene el retorno inmediato para posiciones idénticas y desplaza la comprobación después de validar/expandir la longitud. Rechaza el caso con `-EINVAL` y libera los locks adquiridos. Los movimientos entre inodes diferentes conservan su tratamiento.

Fuentes primarias:

- Upstream: [28c1ef094e7c86977d9bf570dc0362fc54e36437](https://github.com/torvalds/linux/commit/28c1ef094e7c86977d9bf570dc0362fc54e36437), incorporado el 4 de agosto de 2026.
- Backport 5.15 utilizado: [7f80a638679056d4a1d9f2a4e6cc455cec19d86a](https://github.com/gregkh/linux/commit/7f80a638679056d4a1d9f2a4e6cc455cec19d86a), incorporado el 14 de septiembre de 2026.
- Archivo de parche: [0015-f2fs-check-expanded-move-range-overlap.patch](../patches/0015-f2fs-check-expanded-move-range-overlap.patch).

También se conservan los metadatos originales publicados. Ambos parches modifican únicamente funciones estáticas de `fs/f2fs/file.c`; no añaden APIs, estructuras ni símbolos exportados. Los helpers y locks requeridos ya existen en esta base. Esto evita introducir una dependencia de interfaces de un kernel más moderno; la compatibilidad del kernel completo todavía exige sus verificaciones habituales.

## Validación de estos cambios

Los dos parches se reaplicaron secuencialmente sin fuzz sobre el archivo anterior y coinciden con las fuentes finales. El snapshot `kernel-source/linux` y el árbol preparado `.cache/linux` contienen el mismo archivo F2FS modificado.

[Las seis pruebas de rangos](../tests/test_f2fs_range_safety.py) compilan las dos funciones C reales con ASan/UBSan. Utilizan `CHATGPT_TEST_SOURCE_ROOT` para probar el mismo árbol que compila CI, con el snapshot como valor de desarrollo. Los stubs modelan resultados de writeback y comprueban la liberación de locks; no simulan un filesystem completo.

1. Fallo del primer writeback: error propagado, sin comenzar collapse ni truncar.
2. Fallo del segundo writeback: error propagado, invalidate lock liberado, sin truncado ni actualización posterior de tamaño.
3. Collapse correcto: conserva el truncado y tamaño esperados.
4. Move de longitud cero sobre el mismo inode con solapamiento: rechazado antes de escribir/intercambiar.
5. Rangos explícitos solapados, pequeños no alineados, posiciones iguales, longitud vacía a EOF y caso sin solapamiento: conservan los resultados previstos.
6. Inodes diferentes: la longitud cero se expande y el movimiento sigue permitido.

La prueba conserva funciones anteriores congeladas: el control negativo de segundo writeback y el de solapamiento con longitud cero fallan sobre ese código y pasan con las correcciones. Estas pruebas no sustituyen una ejecución del kernel ni una prueba de integridad sobre un volumen montado. No requieren reformatear ni añadir pruebas destructivas al teléfono del usuario.

Checkpatch no encontró errores de código. Emitió cinco avisos de metadatos en total: referencias a commits que no están en la historia local y la diferencia entre el correo de autor y el correo del Signed-off-by original de 0014. Se conservan tal como los publicó stable; no se inventan firmas ni se reescribe esa procedencia para ocultar los avisos.

## Cambios SSG revisados y descartados

La candidata retiene los parches propios 0008/0009 de RCU, sysfs y capacidad de metadatos. Esta revisión no incorpora nuevas constantes ni declara resueltos todos los defectos de SSG.

| Fuente pública | Decisión para esta base |
| --- | --- |
| [e872015d: corregir NULL tras lookup](https://github.com/techyguyperplexable/synthetica_/commit/e872015d02cb214e26da8be3dec72bcd96432561) | No importarlo: nuestra `blkg_to_pd()` ya comprueba NULL antes de acceder a `blkg->pd`. |
| [eb0a755a: doble conversión de jiffies](https://github.com/Kuroringo97/android_kernel_xiaomi_mondrian/commit/eb0a755a8ee6cf1a092e057f52843877b01a2d68) | No importarlo: R10 ya asigna `read_expire` directamente, sin `msecs_to_jiffies()` adicional. |
| [80f9e02c: metadatos y parámetros](https://github.com/Kuroringo97/android_kernel_xiaomi_mondrian/commit/80f9e02cde24aa5a468686f5a99b55bcf456bbb3) | No importar el conjunto: mezcla correcciones con nuevos tiempos/umbrales de otro dispositivo. `BLK_SEC_STATS` no está activo aquí y nuestro 0009 ya maneja capacidad/fallos parciales con garantías diferentes. |
| [cf900cb1: revertir una optimización de next_rq](https://github.com/techyguyperplexable/synthetica_/commit/cf900cb1b871566da33537ccd5e7b249589a530e) | Mantener los resets existentes en R10; eliminarlos había dejado datos obsoletos en ese repositorio. |

Siguen pendientes el tiempo de vida de `blkg` retenido por peticiones y la contabilidad compartida entre hctx. No se añade aisladamente un par `blkg_tryget()`/`blkg_put()`: los metadatos indexados solo por `internal_tag` pueden coincidir entre hctx y antes debe garantizarse la asociación de cada petición con sus propios datos/referencias.

La búsqueda también revisó el [hilo español de WildAngel](https://www.htcmania.com/showthread.php?p=34752119), anuncios públicos de las comunidades de tapas/topaz y repositorios en inglés. El anuncio histórico de un port SSG no proporciona una comparación controlada aplicable a esta ROM. WildAngel documentó desactivar BTF, decisión que este proyecto no adopta. El acceso a contenidos completos de algunos canales indonesios y 4PDA estuvo limitado; no se afirma haber auditado toda la comunidad global.

Tampoco se duplican arreglos F2FS que R10 ya contiene: [UAF de merge_page_bio](https://github.com/torvalds/linux/commit/edf7e9040fc52c922db947f9c6c36f07377c52ea), los [arreglos](https://github.com/torvalds/linux/commit/dd3114870771562036fdcf5abe813956f36d224d) de [deadlock de GC](https://github.com/torvalds/linux/commit/8b4468ec023d0d1b4669dfb867588997cc03a06b) y [GC previo a la asignación LFS](https://github.com/torvalds/linux/commit/1005a3ca28e90c7a64fa43023f866b960a60f791).
