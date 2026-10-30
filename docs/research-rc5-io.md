# Investigación I/O posterior a rc4

Estado: candidatos condicionados a los registros del teléfono. No se ha preparado ni compilado una nueva entrega I/O. Revisión sobre rc4, HEAD `1ebf69612`, base R10 `d246c8c17548bb1a2756092cabf34d11eedcde8c`.

**Decisión: esperar `/data`, cola de almacenamiento y PSI antes de añadir cambios.** Los dos defectos F2FS siguientes ya existían en R10 y rc4: no explican por sí solos que rc4 se perciba igual o peor. Su posible efecto es reducir trabajo writeback excesivo o evitar falta de progreso, sin mejoras medidas de TikTok, temperatura o batería.

## Fuentes y caminos realmente presentes

- `CONFIG_F2FS_FS=y`, `CONFIG_F2FS_STAT_FS=y`, `CONFIG_F2FS_IOSTAT=y` y `CONFIG_F2FS_UNFAIR_RWSEM=y`. Falta conocer el filesystem y las opciones de montaje de `/data`: `mode`, `fsync_mode`, `background_gc`, `gc_merge` y selección IPU. Si usa ext4, estos candidatos no afectan su carga habitual sobre userdata.
- `CONFIG_MQ_IOSCHED_SSG=y`, `CONFIG_MQ_IOSCHED_SSG_CGROUP=y`, `CONFIG_MQ_SSG_DEFAULT=y`. Eso no prueba que SSG sea el scheduler activo de la cola física. Los UFS core/HPB están compilados; `CONFIG_SCSI_UFS_QCOM` no está activo en este Image, por lo que no se debe confundir su fuente con los módulos Qualcomm que pueda cargar el vendor.
- `CONFIG_ZRAM=y`, compresor predeterminado `lz4kd`, `CONFIG_ZRAM_WRITEBACK` desactivado y páginas ARM64 de 4 KiB. La ROM puede elegir otro compresor al inicializar zRAM. El swap-in comprimido ejecuta `__zram_bvec_read()` → `zcomp_decompress()` → Crypto/LZ4KD en CPU/RAM; no pasa por UFS. Un cambio de scheduler de disco no acelera directamente esa descompresión.
- El diff de rc3-rebuild1 a rc4 no cambia zRAM, zcomp, zsmalloc, LZ4KD, UFS ni SSG. Los cambios F2FS de rc4 están limitados a collapse/move range, no a los caminos generales GC/DIO/fsync examinados.

## Candidato 1: contabilizar IPU writeback correctamente

Primario: [6d1f622b9c069378cdb83088be2b15a9b480b8a3](https://github.com/torvalds/linux/commit/6d1f622b9c069378cdb83088be2b15a9b480b8a3), incorporado el 19 de octubre de 2026, `f2fs: fix submit accounting for IPU writeback`.

Ausencia comprobada: `fs/f2fs/segment.c:3669` no marca una escritura IPU correcta como enviada. `fio.submitted` comienza en false (`data.c:2821`), determina el resultado devuelto al llamador (`2947`) y el débito de `wbc->nr_to_write` (`3161`). Por tanto, una escritura IPU correcta puede contar cero y el writeback asíncrono superar su presupuesto.

Diff mínimo que habría que adaptar y validar:

```diff
 if (!err) {
+    fio->submitted = 1;
     f2fs_update_device_state(...);
```

Usa un campo y helpers existentes. No necesita cambios de configuración, estructuras, firmas o exports. Es el primer candidato si los registros confirman F2FS y presión de writeback/I/O relevante. No se localizó un backport oficial 5.15 en el historial consultado; correspondería documentarlo como adaptación propia del arreglo upstream.

Prueba recomendada: extraer la función C real y modelar IPU combinado/directo correctos, error de envío y checkpoint roto. Exigir `submitted=1` solo al éxito. Añadir un presupuesto de N páginas para comprobar que N envíos correctos lo agotan; el código anterior debe fallar ese control. No requiere pruebas destructivas en el teléfono.

## Candidato 2: progreso entre inodes sucios durante checkpoint

Primario: [e398da0b9131583e0f52bca733eaefc3b3aeae95](https://github.com/torvalds/linux/commit/e398da0b9131583e0f52bca733eaefc3b3aeae95), incorporado el 14 de septiembre de 2026, `f2fs: fix livelock in syncing dirty inodes`.

Ausencia comprobada: `checkpoint.c:1117` y `1166` toman la cabeza de `dirty_list`/`gdirty_list` sin rotarla antes de `igrab()`. Si ese inode está liberándose, los demás pueden quedar sin progreso; el camino de metadatos tampoco cede CPU cuando falla `igrab()`.

Núcleo del cambio:

```diff
 fi = list_first_entry(..., dirty_list);
+list_move_tail(&fi->dirty_list, head);
 inode = igrab(...);
```

Se aplica también a `gdirty_list`, con `cond_resched()` en el fallo del camino de metadatos. No añade campos ni interfaces; debe conservar la visibilidad y firma actuales de las funciones. El upstream también retira un flush redundante. La base entrega OPU/IPU al terminar `.writepages` (`data.c:3222–3226`), pero retirar ese flush exige comprobar el conjunto y no copiar el parche sin adaptación. Tampoco se localizó un backport oficial 5.15 en la consulta.

Prueba recomendada: listas con inode A liberándose e inode B válido; B debe progresar antes de que A deje de fallar. Comprobar ambos listados, locks y cesión de CPU. Usar límite de iteraciones en el control negativo para detectar la falta de progreso sin colgar el ensayo.

## Descartes y límites de esta revisión

- **Backports GC/DIO ya presentes:** [edf7e904](https://github.com/torvalds/linux/commit/edf7e9040fc52c922db947f9c6c36f07377c52ea), [dd311487](https://github.com/torvalds/linux/commit/dd3114870771562036fdcf5abe813956f36d224d), [8b4468ec](https://github.com/torvalds/linux/commit/8b4468ec023d0d1b4669dfb867588997cc03a06b) y [1005a3ca](https://github.com/torvalds/linux/commit/1005a3ca28e90c7a64fa43023f866b960a60f791). No duplicarlos ni atribuirles una mejora nueva.
- **Mutex/preemption moderno de zRAM:** la base sigue usando `local_lock`, con preemption desactivada en este kernel no RT. No contiene [2efa9e9e](https://github.com/torvalds/linux/commit/2efa9e9eb4db2725c9f419f241cb0e09fc3d8574), que introdujo streams con mutex. El [RFC sobre inversión de prioridad Android](https://lists.openwall.net/linux-kernel/2026/08/05/70) y la serie moderna de streams compartidos corrigen otro diseño. No son una solución pequeña trasladable a esta base.
- **LZ4KD e incomprimibles:** [8c333fec](https://github.com/FlopKernel-Series/flop_exynos2100_kernel/commit/8c333feccb6f227d58e23a2ee0adbf6db405fa84) corrige backends modernos que trataban `ret==0` como error. Aquí `crypto/lz4kd.c` solo rechaza `ret<0`; con cero conserva el tamaño de destino de dos páginas y zRAM selecciona almacenamiento sin comprimir. No está el defecto descrito ni se justifica copiar otro fallback con memcpy.
- **Skip-swapcache síncrono ya presente:** `mm/memory.c:3818` utiliza `SWP_SYNCHRONOUS_IO` y el camino `swap_readpage(page, true)`. No reaplicar la optimización histórica ni prometer otra reducción de latencia por ella.
- **SSG:** persisten las cuestiones de identidad de metadatos entre hctx y referencias `blkg` retenidas por peticiones. Esta revisión no amplía ese alcance. SSG indexa solo por `internal_tag`; la cola SCSI usa un hctx por defecto, pero el hook vendor MCQ puede cambiarlo. Deben comprobarse scheduler activo y `/sys/block/sd*/mq/` antes de relacionarlo con este teléfono. No se propone cambiar a otro scheduler ni sus tiempos/umbrales ahora.

Los registros útiles para decidir son el montaje/opciones de `/data`, scheduler y número de colas físicas, deltas de diskstats y PSI de I/O, y zRAM `mm_stat`, `io_stat`, `debug_stat` junto a `pswpin/pswpout`. `debug_stat` aporta `writestall`, ausente de los otros dos archivos. Correlacionar esos datos puede orientar la siguiente intervención; no atribuye por sí solo cada microtirón a disco o descompresión.

No se editaron fuentes, configuración ni CI, ni se ejecutaron compilaciones durante esta investigación. La única salida nueva es este dossier.
