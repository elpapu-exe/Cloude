# Revisión internacional y decisiones de rc4

**Candidata 0.1.0-rc4: pendiente de compilación completa y publicación.** Se revisaron fuentes primarias de Linux/Android, repositorios comunitarios y anuncios en distintos idiomas. La revisión se contrastó con esta base Zepharo R10 / Linux 5.15.216, para Redmi Note 12 4G TAPAS/topaz y Android 13. No cubre toda la comunidad mundial y no incluye una comparación controlada en el teléfono.

La [entrega anterior rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) está publicada y tiene sus propias fuentes, hashes y resultados. Sus comprobaciones no se atribuyen a rc4. Tampoco es el binario rc3 histórico que quedó inaccesible.

## Seis correcciones seleccionadas

| Parche | Error presente y cambio acotado | Fuente primaria |
| --- | --- | --- |
| 0010, MGLRU | El reintento restaba páginas que podían no haberse contado tras fallar su bloqueo. Se elimina la resta para evitar desbordamiento y una posible división por cero al calcular presión. | [8b671fe1a879](https://github.com/torvalds/linux/commit/8b671fe1a879923ecfb72dda6caf01460dd885ef) |
| 0011, MGLRU | El recorrido vecino de PTE no excluía VMA especiales. Se añade ese guard, conservando el comportamiento de las VMA normales. | [c28ac3c7eb94](https://github.com/torvalds/linux/commit/c28ac3c7eb945fee6e20f47d576af68fdff1392a) |
| 0012, Binder | La comprobación de cuota todavía incluía metadatos que el débito ya excluía. Se evita rechazar una petición que sí cabe en la cuota restante, manteniendo el vendor hook. | [c6d05e0762ab](https://github.com/torvalds/linux/commit/c6d05e0762ab276102246d24affd1e116a46aa0c) |
| 0013, CPUfreq | El inicio de schedutil/Horizon podía sobrescribir una demora nueva publicada mediante sysfs. Se serializan las lecturas y asignaciones con el mutex existente. | [ce390caf5541](https://github.com/torvalds/linux/commit/ce390caf5541c493c9061e7a2d98a463e66b736a) |
| 0014, F2FS | `collapse_range` ignoraba el error del segundo writeback. Se propaga y se evita continuar con el truncado y la actualización posterior de tamaño en ese camino. | [f8a410880025](https://github.com/torvalds/linux/commit/f8a4108800254d6f7b2755515fbbd9d0caac561e), [backport 5.15](https://github.com/gregkh/linux/commit/4adebfe52db633992b35cc183e2520cf0c2b56bf) |
| 0015, F2FS | `MOVE_RANGE` comprobaba solapamiento antes de expandir `len=0` hasta EOF. La comprobación se mueve después de calcular la longitud efectiva. | [28c1ef094e7c](https://github.com/torvalds/linux/commit/28c1ef094e7c86977d9bf570dc0362fc54e36437), [backport 5.15](https://github.com/gregkh/linux/commit/7f80a638679056d4a1d9f2a4e6cc455cec19d86a) |

Las adaptaciones conservan los hooks y APIs existentes; no añaden estructuras ni símbolos exportados. La compatibilidad completa de ABI todavía debe comprobarse en la nueva compilación. CPUfreq actúa en los gobernadores presentes; schedutil continúa como predeterminado. F2FS solo cambia los caminos indicados cuando se utiliza ese filesystem: no se conoce aún si `/data` del usuario usa F2FS o ext4.

Los detalles de aplicación, dependencias, pruebas y descartes están en [memoria/Binder](research-rc4-memory.md), [CPUfreq](research-rc4-cpufreq.md) y [almacenamiento/SSG](research-rc4-storage.md). Las pruebas compilan funciones C reales con ASan/UBSan, intercalados modelados y controles negativos del comportamiento anterior. No son pruebas del kernel arrancado ni mediciones de fluidez.

## Retirada del ajuste experimental de memoria

El parche 0016 restaura **`watermark_scale_factor=10`**, inicializador de la base, frente al 64 introducido por 0004. No había una medición controlada que justificase 64 como política general para TAPAS/A13. La restauración reduce el alcance de ajustes experimentales; no se presenta como una mejora demostrada de rendimiento.

La ROM o los módulos pueden sobrescribir el valor después del arranque. Un valor runtime distinto del compilado no demuestra que el inicializador esté mal. La prueba del teléfono registra el valor observado junto con PSI, reclaim, zRAM y temperatura.

## Otras fuentes comunitarias consultadas

| Fuente | Resultado para esta candidata |
| --- | --- |
| [Zepharo, rama `zepharo`](https://github.com/topnotchfreaks/kernel_msm-5.15/tree/zepharo), [issue 27](https://github.com/topnotchfreaks/kernel_msm-5.15/issues/27), [issue 24](https://github.com/topnotchfreaks/kernel_msm-5.15/issues/24) | El informe de compilación de eventpoll no coincide con un fallo actual observado. La petición de configuración BBR no demuestra una mejora de cambios entre aplicaciones. Se conserva la base y se revisan errores concretos. |
| [ChicKernel: fuentes y README](https://github.com/ChicKernel/device_xiaomi_gemstones-kernel), [hilo XDA 4678538](https://xdaforums.com/t/4678538/) | Los arreglos USB/fuel gauge examinados ya están en R10. No se duplican ni se importan cambios térmicos dependientes de XML/vendor concretos o filtros de kmsg que oculten errores. |
| [TenSeventy7/tnsvn-tapaz-plus](https://github.com/TenSeventy7/tnsvn-tapaz-plus) | Sus ajustes WALT/MIUI no son una receta portable para esta candidata: `CONFIG_SCHED_WALT` está desactivado y la referencia del usuario es LineageOS 20 A13. |
| [Anuncios públicos topazkerneldump](https://t.me/s/topazkerneldump?before=429) | Se leyeron anuncios de XStock, Kaze y Zepharo R9. No aportan una comparación A/B controlada aplicable a esta ROM; no se convierten en promesas de rendimiento. |
| [Hilo de 4PDA](https://4pda.to/forum/index.php?showtopic=1072135&st=6660) | El acceso al contenido completo respondió HTTP 403. Solo estuvieron disponibles fragmentos indexados: no se declara una inspección completa ni se extraen conclusiones técnicas firmes de ellos. |

También se descartó duplicar la contabilidad de workingset que ya usa esta base, reincorporar el arreglo CAS de 0007, importar el RFC amplio de swappiness MGLRU o sustituir lz4kd sin un fallo demostrado. Los detalles y referencias están en los dossiers anteriores. Los problemas restantes de tiempo de vida de `blkg` y contabilidad multi-hctx de SSG siguen abiertos; los parches 0008/0009 no se presentan como una solución completa.

## Qué conserva la candidata y cómo evaluarla

Se conservan CFI, Full LTO/O2, Shadow Call Stack, BTF, MODVERSIONS, protecciones térmicas, root y la compatibilidad prevista con los módulos necesarios. No se cambian tamaño/compresor de zRAM, LMKD, swappiness, frecuencias o voltajes. La identidad exacta de la fuente SUSFS de R10 sigue sin demostrarse; el candidato histórico fijado mantiene ese límite de procedencia.

Antes de entregar rc4 deben pasar compilación ARM64, configuración embebida, símbolos/CRC, auditoría del tar final, listado SHA256SUMS y descarga de los assets. Después se comprueban arranque y funciones básicas, conservando WhatsApp y los módulos del usuario, y se ejecuta la [comparación breve](testing.md). Los arreglos seleccionados tienen razones verificables en código; todavía no se ha demostrado que reduzcan los ANR, tirones, temperatura o consumo de batería en el teléfono.
