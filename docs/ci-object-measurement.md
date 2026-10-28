# Medición de objetos y presupuesto del runner

Esta medición corresponde a **0.1.0-rc3-rebuild1**, una reconstrucción nueva. El registro estructurado está en [ci-object-measurement.json](ci-object-measurement.json). No recupera ni identifica el binario rc3 histórico.

## Resultado medido

`make ... -j2 descend` terminó con código **0** en **883 segundos (14 min 43 s)**. Este target recorre los directorios normales de objetos; el enlace global se ejecuta después, desde `scripts/link-vmlinux.sh`, y no se intentó aquí. Se reutilizó un directorio `out` configurado que contenía objetos previos: no fue una reconstrucción limpia.

| Concepto | Resultado |
| --- | ---: |
| Archivos `.o` al terminar | 2.985 |
| Objetos LLVM IR bitcode | 2.795 |
| Objetos ELF AArch64 | 117 |
| Objetos ELF del host x86_64 | 71 |
| Otros objetos ELF | 2 |
| Tamaño aparente de todos los `.o` | 845.149.760 bytes |
| Archivos `.a` | 734; 732 son thin archives |
| Espacio asignado final y máximo observado de `out` | 1.151.901.696 bytes ≈ 1,073 GiB |
| Fuentes, herramientas y descargas en `.cache` | 2.143.612.928 bytes ≈ 1,996 GiB |
| Máximo observado de `memory.current` del cgroup | 4.111.265.792 bytes ≈ 3,829 GiB |
| Límite de memoria del cgroup local | 8 GiB; sin swap |

La memoria se muestreó cada diez segundos, con 89 muestras. Incluye caché de páginas y otros procesos del entorno compartido: **no es el pico RSS exclusivo del compilador** y puede omitir picos breves. Esta cifra tampoco mide la memoria del enlace Full LTO.

La configuración efectiva tiene SHA-256 `959f9931856597bc5219a68392c77334887315c8e53e30a039f52b82dfaa3cc7`. Conserva Full LTO, CFI, Shadow Call Stack, BTF y MODVERSIONS. `verify-config.py` aprobó también las comprobaciones térmicas y de KSU. El JSON registra hashes de configuración, entradas, nueve parches y registros para vincular los tamaños a esta carga concreta.

## Qué falta medir

El enlace mantiene simultáneamente tres salidas grandes con DWARF: `vmlinux.o`, `.tmp_vmlinux.btf` y `vmlinux`. Sus tamaños **no están medidos**. Los ELF temporales de kallsyms se enlazan con `--strip-debug`; sus tamaños exactos tampoco se han medido. Los thin archives referencian los objetos y no duplican su contenido completo.

La imagen rc1 de 47.520.256 bytes elimina información de depuración; su tamaño no permite deducir el tamaño de esos ELF. Esta fase tampoco hizo generación de BTF, empaquetado, comparación de exports ni validación en el teléfono.

## Presupuesto para un ensayo instrumentado

El margen anterior de 45 GiB era conservador y no procedía de una medición de disco de este proyecto. La fase de objetos ya medida permite plantear un ensayo con **15 GiB libres después de provisionar swap**, manteniendo las protecciones. Se separan las mediciones de las asignaciones de presupuesto:

| Componente | GiB | Base |
| --- | ---: | --- |
| Fuentes, herramientas y descargas | 1,996 | Medido localmente |
| `out` antes del enlace | 1,073 | Medido localmente |
| Imagen Docker y dependencias de arranque | 2,000 | Asignación estimada; sin medir en el runner final |
| Fuentes comprimidas, ZIP y registros | 1,000 | Asignación estimada; sin medir para esta entrega |
| Kallsyms y mapas temporales | 0,500 | Asignación estimada |
| Espacio que conserva la vigilancia de disco | 2,000 | Umbral para detener la fase |
| Remanente para los tres ELF con DWARF | **6,431** | Presupuesto disponible; tamaño real desconocido |

Ese remanente **no es un límite superior demostrado ni una garantía de que el enlace quepa**. La vigilancia detiene el grupo de procesos de la fase si el espacio libre baja de 2 GiB. El siguiente intento debe registrar el consumo real para sustituir estas asignaciones por medidas.

El plan de memoria calcula la swap adicional desde RAM disponible, swap utilizable y límites de cgroup: apunta a **37 GiB disponibles combinados**, incluyendo 1 GiB de margen de arranque, y exige al menos **36 GiB** al verificar los recursos reales. El antecedente cercano a 32 GiB durante Full LTO justifica reservar más memoria que en la fase de objetos; no demuestra que ese margen baste. La swap puede hacer que el enlace exceda el tiempo del job.

El runner privado observado tenía 2 CPU, unos 7,75 GiB de RAM y un único volumen raíz de 71,6 GiB; `/mnt` compartía ese volumen. La receta evita el checkout duplicado de las fuentes, comprueba recursos antes y después de limpiar SDKs prescindibles únicamente en el runner desechable y registra el espacio efectivamente recuperado. No se cuenta como recuperable todo el tamaño de un directorio sin observar el resultado de la limpieza.

Un ensayo que falle por espacio, memoria, tiempo, compilación o auditoría no debe publicar un kernel. Completar la compilación y sus verificaciones tampoco certifica arranque, estabilidad o fluidez en TAPAS.
