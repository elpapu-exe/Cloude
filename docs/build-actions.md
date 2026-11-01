# Compilar y entregar con GitHub Actions

El workflow `Build and deliver ChatGPT Kernel` conserva ZIP, configuración efectiva, hashes, registros por fase, comparación de exports y fuentes correspondientes. Usa Debian 13 fijado por digest, Clang y entradas fijadas por SHA-256. Full LTO, CFI, Shadow Call Stack, BTF, MODVERSIONS y térmicas siguen siendo obligatorios.

## Uso

En Actions, **Run workflow** sobre `chatgpt-kernel-download` permite seleccionar el runner y la swap. Un cambio en `.github/build-request.json` de esa rama también inicia el trabajo. Valores predeterminados: runner `"ubuntu-24.04"`, swap `auto`, dos trabajos de compilación. Se pueden configurar `KERNEL_RUNNER_JSON`, `KERNEL_SWAP_GIB` y `KERNEL_JOBS`.

El usuario no necesita compilar en Windows. El perfil del runner estándar es un **ensayo instrumentado**, no una certificación anticipada de capacidad. La alternativa de un runner propio sigue admitida por sus etiquetas JSON, si realmente existe; los runners mayores de GitHub tienen restricciones de plan y organización y no aparecen por cambiar una etiqueta.

## Recursos y fases

La primera receta falló antes de compilar con 32 GiB de swap adicional y un margen conservador de 45 GiB de disco. El runner privado observado tenía 7,75 GiB de RAM y un solo volumen raíz de 71,6 GiB, compartido con `/mnt`. Aquel margen de 45 GiB no procedía de un pico de disco medido del kernel.

Se midió posteriormente la fase completa de objetos ARM64: 2.985 objetos, `out/` de 1,073 GiB y entradas de 1,996 GiB, sin enlace global. [Medición, presupuesto y límites](ci-object-measurement.md). El perfil `hosted_compact` de `config/ci-resources.json` permite probar con 15 GiB libres después de swap, manteniendo 2 GiB de reserva vigilada. La rc5 completó el enlace con este perfil; otros intentos siguen sujetos a las comprobaciones de espacio, memoria y tiempo.

Solo en runners Linux desechables de GitHub se eliminan rutas concretas de SDKs que este build C dentro del contenedor no utiliza. El inventario antes/después registra el espacio realmente recuperado. Se utiliza `/usr/bin/python3`; no se eliminan los runtimes internos del runner. Se podan únicamente imágenes Docker sin contenedores antes de obtener la imagen fijada. No se borran volúmenes Docker.

El checkout parcial evita duplicar las fuentes, que se adquieren y verifican en `.cache/`. Las pruebas de helpers se ejecutan contra ese mismo árbol compilado mediante `CHATGPT_TEST_SOURCE_ROOT`.

La swap `auto` cubre el déficit calculado hasta 37 GiB disponibles combinados, incluido 1 GiB de arranque; se exigen 36 GiB utilizables al comprobar la capacidad real. El plan comprueba los sistemas de archivos de trabajo, swap y Docker, y vuelve a medir tras activar swap, incluyendo límites de cgroup. Los runners propios no reciben limpiezas ni swap nueva y conservan el margen de disco de 45 GiB.

Las fases visibles son preparación, compilación de objetos, enlace Full LTO/Image y auditorías. Se registran recursos/PSI cada 15 segundos y espacio/tamaños de salidas cada dos segundos en objetos/enlace. Si la reserva de disco baja de 2 GiB, se detiene el grupo de procesos de la fase. La swap puede ser lenta; el job conserva el límite de seis horas. Todo fallo bloquea la publicación.

## Entrega

Los artefactos y logs de Actions se conservan 90 días, incluso cuando falla la construcción. La publicación usa un job separado con `contents: write`; el contenedor de compilación no recibe un token de GitHub.

Después de verificar imagen/configuración/ABI, se ejecutan las 93 regresiones obligatorias sin omisiones y se audita el archivo final de fuentes por contenido, tipo, modo y destino literal de symlink. Un listado cerrado SHA256SUMS cubre todos los assets.

La prerelease se crea como borrador con tag único. Se vuelven a descargar todos sus archivos, se comprueban sus hashes y solo entonces se publica. El tar de fuentes se conserva como asset y artefacto, fuera del historial Git normal. Las fuentes comprimidas excluyen `.git`; la receta obtiene las historias originales fijadas necesarias para reconstruir, especialmente la de KSU.

`0.1.0-rc5` está [publicada y verificada](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc5-9c81476ba0a6-41290063824); rc4 conserva su entrega anterior. [Resultado propio](ci-build-result-rc5.json). Una compilación y sus auditorías no certifican arranque, estabilidad, temperatura ni fluidez en TAPAS.

## Ejecución completada

El perfil compacto terminó correctamente en el [run 40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058), desde a01d67ebe63f98a705c068ea735f9ae87848b35c. Se crearon 28 GiB de swap adicional y quedaron 19.439.857.664 bytes de trabajo tras provisionarla. La fase de objetos duró 27 min 40 s y Full LTO/Image 44 min. Se completaron las auditorías y la publicación con descarga verificada. Los [resultados](ci-build-result.json) registran los recursos observados; el éxito de esta carga no garantiza otras configuraciones ni elimina la validación del teléfono.

La rc5 completó objetos en 19 min 6 s y Full LTO/Image en 52 min 15 s, con dos CPU, aproximadamente 7,75 GiB de RAM y 28 GiB de swap adicional. Pasaron 93 pruebas, ABI y auditoría final de fuentes; se verificaron los 35 assets descargados antes de publicar. Las 33 pruebas y el recolector v7 del módulo CPU pertenecen a su ejecución independiente.
