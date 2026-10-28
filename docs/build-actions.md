# Compilar y entregar con GitHub Actions

El workflow `Build and deliver ChatGPT Kernel` conserva ZIP, configuración efectiva, hashes, registros por fase, comparación de exports y fuentes correspondientes. Usa Debian 13 fijado por digest, Clang y entradas fijadas por SHA-256. Full LTO, CFI, Shadow Call Stack, BTF, MODVERSIONS y térmicas siguen siendo obligatorios.

## Uso

En Actions, **Run workflow** sobre `chatgpt-kernel-download` permite seleccionar el runner y la swap. Un cambio en `.github/build-request.json` de esa rama también inicia el trabajo. Valores predeterminados: runner `"ubuntu-24.04"`, swap `auto`, dos trabajos de compilación. Se pueden configurar `KERNEL_RUNNER_JSON`, `KERNEL_SWAP_GIB` y `KERNEL_JOBS`.

El usuario no necesita compilar en Windows. El perfil del runner estándar es un **ensayo instrumentado**, no una certificación anticipada de capacidad. La alternativa de un runner propio sigue admitida por sus etiquetas JSON, si realmente existe; los runners mayores de GitHub tienen restricciones de plan y organización y no aparecen por cambiar una etiqueta.

## Recursos y fases

La primera receta falló antes de compilar con 32 GiB de swap adicional y un margen conservador de 45 GiB de disco. El runner privado observado tenía 7,75 GiB de RAM y un solo volumen raíz de 71,6 GiB, compartido con `/mnt`. Aquel margen de 45 GiB no procedía de un pico de disco medido del kernel.

Se midió posteriormente la fase completa de objetos ARM64: 2.985 objetos, `out/` de 1,073 GiB y entradas de 1,996 GiB, sin enlace global. [Medición, presupuesto y límites](ci-object-measurement.md). El perfil `hosted_compact` de `config/ci-resources.json` permite probar con 15 GiB libres después de swap, manteniendo 2 GiB de reserva vigilada. Los tres ELF grandes del enlace aún no se han medido; el ensayo puede detenerse por espacio, memoria o tiempo.

Solo en runners Linux desechables de GitHub se eliminan rutas concretas de SDKs que este build C dentro del contenedor no utiliza. El inventario antes/después registra el espacio realmente recuperado. Se utiliza `/usr/bin/python3`; no se eliminan los runtimes internos del runner. Se podan únicamente imágenes Docker sin contenedores antes de obtener la imagen fijada. No se borran volúmenes Docker.

El checkout parcial evita duplicar las fuentes, que se adquieren y verifican en `.cache/`. Las pruebas de helpers se ejecutan contra ese mismo árbol compilado mediante `CHATGPT_TEST_SOURCE_ROOT`.

La swap `auto` cubre el déficit calculado hasta 37 GiB disponibles combinados, incluido 1 GiB de arranque; se exigen 36 GiB utilizables al comprobar la capacidad real. El plan comprueba los sistemas de archivos de trabajo, swap y Docker, y vuelve a medir tras activar swap, incluyendo límites de cgroup. Los runners propios no reciben limpiezas ni swap nueva y conservan el margen de disco de 45 GiB.

Las fases visibles son preparación, compilación de objetos, enlace Full LTO/Image y auditorías. Se registran recursos/PSI cada 15 segundos y espacio/tamaños de salidas cada dos segundos en objetos/enlace. Si la reserva de disco baja de 2 GiB, se detiene el grupo de procesos de la fase. La swap puede ser lenta; el job conserva el límite de seis horas. Todo fallo bloquea la publicación.

## Entrega

Los artefactos y logs de Actions se conservan 90 días, incluso cuando falla la construcción. La publicación usa un job separado con `contents: write`; el contenedor de compilación no recibe un token de GitHub.

Después de verificar imagen/configuración/ABI, se ejecutan las 50 regresiones obligatorias sin omisiones y se audita el archivo final de fuentes por contenido, tipo, modo y destino literal de symlink. Un listado cerrado SHA256SUMS cubre todos los assets.

La prerelease se crea como borrador con tag único. Se vuelven a descargar todos sus archivos, se comprueban sus hashes y solo entonces se publica. El tar de fuentes se conserva como asset y artefacto, fuera del historial Git normal. Las fuentes comprimidas excluyen `.git`; la receta obtiene las historias originales fijadas necesarias para reconstruir, especialmente la de KSU.

`0.1.0-rc3-rebuild1` es una reconstrucción nueva. Una compilación y sus auditorías no certifican arranque, estabilidad, temperatura ni fluidez en TAPAS.
