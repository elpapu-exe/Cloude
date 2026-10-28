# Revisión de memoria y Binder para la candidata rc4

Esta investigación revisa fuentes primarias de Linux y Android en inglés, con aportaciones de mantenedores de Google y del kernel, además de comprobar el código local. No pretende cubrir toda la comunidad internacional ni demostrar superioridad frente a todos los kernels TAPAS. El punto de partida es Linux 5.15.216 / Zepharo R10 `d246c8c17548bb1a2756092cabf34d11eedcde8c`, con la serie reconstruida 0001–0009 de ChatGPT Kernel. No recupera el binario rc3 histórico ni hereda sus validaciones.

Se seleccionaron tres correcciones pequeñas de errores presentes en esa base. No son ajustes nuevos de zRAM, swappiness, LMKD, frecuencias o temperatura. Ninguna demuestra la causa concreta de los ANR o tirones del teléfono.

## 0010: contabilidad de escaneo al reintentar páginas MGLRU

Fuente primaria: [8b671fe1a879923ecfb72dda6caf01460dd885ef, “mm/mglru: fix div-by-zero in vmpressure_calc_level()”](https://github.com/torvalds/linux/commit/8b671fe1a879923ecfb72dda6caf01460dd885ef), de Yu Zhao, integrado por Andrew Morton. [Discusión original](https://lore.kernel.org/20240711191957.939105-1-yuzhao@google.com/).

En esta base, `shrink_page_list()` salta una página si falla `trylock_page()`, antes de incrementar `sc->nr_scanned`. Si posteriormente la página está desbloqueada y limpia, `evict_pages()` puede moverla al grupo de reintento y restar `thp_nr_pages(page)`, aunque no hubiera sido contabilizada. Otro fallo de bloqueo durante el reintento puede dejar el contador desbordado. `vmpressure_calc_level()` todavía calcula `scale = scanned + reclaimed` y divide por `scale`; por ejemplo, `scanned = ULONG_MAX` y `reclaimed = 1` producen un divisor cero.

La adaptación elimina exclusivamente esa resta, igual que upstream hace en la implementación con folios. Conserva el reintento, las decisiones de rechazo, el vendor hook, los contadores de páginas recuperadas y el resto del flujo. El contador de escaneo puede incluir el segundo intento: upstream acepta ese doble cómputo antes que una resta sin una relación demostrable con el primer incremento.

No cambia estructuras, prototipos, símbolos exportados, configuración o límites térmicos. No depende de incorporar las APIs modernas de folios. Es distinta del arreglo 0007, que conserva el tipo anon/file observado por el CAS de generación.

## 0011: excluir VMA especiales del lookaround MGLRU

Fuente primaria: [c28ac3c7eb945fee6e20f47d576af68fdff1392a, “mm/mglru: skip special VMAs in lru_gen_look_around()”](https://github.com/torvalds/linux/commit/c28ac3c7eb945fee6e20f47d576af68fdff1392a), de Yu Zhao, integrado por Andrew Morton. [Informe syzbot citado por upstream](https://lore.kernel.org/000000000000f9ff00060d14c256@google.com/).

Las VMA especiales, por ejemplo `VM_PFNMAP`, pueden contener páginas anónimas creadas por COW. El recorrido general de tablas de páginas ya excluye `VM_SPECIAL` en esta base, pero el recorrido vecino de `lru_gen_look_around()` no lo hacía. Ese camino podía alcanzar la advertencia por `pte_special()` en `get_pte_pfn()` sin una ganancia útil de recuperación.

La adaptación añade únicamente la comprobación `pvmw->vma->vm_flags & VM_SPECIAL` antes de recorrer los PTE. Conserva el retorno por contención del PTL y el comportamiento para VMA normales. No introduce el refactor a folios del contexto upstream ni modifica interfaces, contadores exportados o vendor hooks.

## 0012: frontera de cuota asíncrona Binder

Fuente primaria: [c6d05e0762ab276102246d24affd1e116a46aa0c, “binder: fix unused alloc->free_async_space”](https://github.com/torvalds/linux/commit/c6d05e0762ab276102246d24affd1e116a46aa0c).

Esta base contiene un backport parcial: el débito de una transacción asíncrona ya resta únicamente `size`, la devolución ya suma `buffer_size`, y la detección de spam ya excluye los metadatos. Sin embargo, el guard previo seguía exigiendo `free_async_space >= size + sizeof(struct binder_buffer)`. Eso rechaza con `-ENOSPC` una petición que sí cabe en la cuota entre `size` y `size + sizeof(buffer) - 1`.

Se completa exclusivamente el guard a `free_async_space < size`. Se conservan alineación, comprobaciones de overflow, tamaño mínimo de parcelas vacías, detección de spam y el vendor hook inmediatamente anterior. El hook mantiene sus argumentos e identidad; puede seguir ajustando la cuota antes de comprobarla. No hay cambios de estructura, protocolo Binder, símbolo exportado ni ABI para Android 13.

La gran recuperación de capacidad descrita por el commit upstream completo no se atribuye a esta adaptación: en estas fuentes los débitos principales ya estaban corregidos. El beneficio justificable se limita a evitar los rechazos en esa frontera.

## Pruebas reproducibles y límites

```sh
python3 tests/test_mglru_reclaim.py
python3 tests/test_binder_async_quota.py
CHATGPT_TEST_SOURCE_ROOT=.cache/linux python3 tests/test_mglru_reclaim.py
CHATGPT_TEST_SOURCE_ROOT=.cache/linux python3 tests/test_binder_async_quota.py
```

`test_mglru_reclaim.py` compila las funciones reales `evict_pages()`, `get_pte_pfn()`, `lru_gen_look_around()` y `vmpressure_calc_level()` con ASan/UBSan. Se modelan las primitivas de listas, bloqueos, páginas y resultados de recuperación; no se reemplaza la lógica de control que se está probando. Sus seis pruebas cubren el intercalado de fallos de bloqueo y reintento, un reintento exitoso con una página compuesta, la lista vacía, rechazos y vendor bypass, las cuatro clases de VMA especiales y los caminos normales/con PTL contendido. Reintroducir la resta anterior produce división por cero bajo UBSan; quitar el guard vuelve a recorrer los PTE especiales y falla los cuatro controles negativos.

`test_binder_async_quota.py` compila el prefijo real de `binder_alloc_new_buf_locked()` hasta el recorrido del árbol de buffers. Comprueba frontera de cuota, parcelas vacías, insuficiencia, llamadas síncronas, alineación/overflow y cambios de cuota mediante el hook. El éxito posterior al guard es una salida explícita de la fixture: no simula el árbol rojo-negro ni certifica toda la asignación Binder. Reintroducir la condición anterior hace fallar los controles negativos. Los tamaños de metadatos de las fixtures son ilustrativos, no una medición del `struct binder_buffer` ARM64 compilado.

Pasar estas pruebas verifica regresiones concretas bajo modelos deterministas. No es una prueba de concurrencia del kernel completo, arranque, interacción con los módulos del usuario o rendimiento en TikTok. La configuración efectiva, los objetos ARM64, exports/CRC, imagen, BTF y fuentes finales deben volver a comprobarse al compilar la candidata. La comprobación de ABI no se considera completada por ausencia de cambios declarados de interfaz.

## Revisión y descartes

- [3af0191a594d5ca5d6d2e3602b5d4284c6835e77, “Multi-gen LRU: fix workingset accounting”](https://github.com/torvalds/linux/commit/3af0191a594d5ca5d6d2e3602b5d4284c6835e77): ya está aplicado funcionalmente. `mm/workingset.c` contabiliza refault antes del filtro de recencia y activation para el caso reciente. No se duplica ni se afirma corregir LMKD mediante un cambio adicional.
- [766f584cb6270dadce62c40c0cd4327aff7d531a, contabilidad anon/file tras CAS](https://github.com/torvalds/linux/commit/766f584cb6270dadce62c40c0cd4327aff7d531a): ya adaptado por 0007; se mantiene su prueba independiente.
- [00a51d09912a12232d47bc282b74397908d1ed5c, contadores `NR_ISOLATED` en MGLRU](https://github.com/torvalds/linux/commit/00a51d09912a12232d47bc282b74397908d1ed5c): no se incorpora aquí. El parche moderno dispone de un contador de páginas aisladas a través de helpers que nuestra implementación no expone al llamador; requiere una adaptación y revisión separadas de reintentos y páginas compuestas.
- La serie reciente [RFC v5 sobre swappiness MGLRU](https://lore.kernel.org/linux-mm/20261022220203.91911-1-baohua@kernel.org/) modifica varias decisiones y depende de una implementación moderna. No se importa una serie experimental amplia como si fuese una mejora medida para este teléfono.
- `CONFIG_ZRAM_WRITEBACK` está desactivado. Los cambios de writeback de zRAM no corresponden a esta configuración. No se encontró en esta revisión acotada un fallo demostrado de lz4kd que justifique sustituir el compresor o variar su tamaño lógico. El consumo físico comprimido sigue siendo una magnitud distinta del tamaño lógico del dispositivo zRAM.
- No se alteran CFI, Full LTO, Shadow Call Stack, BTF, MODVERSIONS, térmicas ni las integraciones necesarias de Android 13. Los módulos personales y WhatsApp se conservan para la comparación posterior en el teléfono.
