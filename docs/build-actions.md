# Compilar y entregar con GitHub Actions

El workflow `Build and deliver ChatGPT Kernel` compila y conserva el ZIP, su configuración efectiva, los hashes, los registros, la comparación de exports y las fuentes correspondientes. La compilación y las verificaciones se ejecutan en Debian 13 fijado por digest, con Clang y dependencias fijadas por SHA-256. Conserva Full LTO, CFI, Shadow Call Stack, BTF y MODVERSIONS; no rebaja protecciones para superar un fallo de recursos.

## Iniciar una compilación

En GitHub, abre **Actions → Build and deliver ChatGPT Kernel → Run workflow** y selecciona `chatgpt-kernel-download`. El campo `runner` acepta JSON: `"ubuntu-24.04"` para probar el runner estándar o `["self-hosted","linux","x64","kernel-40g"]` si existe un runner propio con esas etiquetas. No se presupone que ese runner esté registrado. Se recomienda disponer de al menos 40 GiB de RAM física y espacio de disco suficiente.

Un cambio en `.github/build-request.json` dentro de `chatgpt-kernel-download` también inicia una compilación y entrega. Para ese disparo se usan las variables del repositorio `KERNEL_RUNNER_JSON` y `KERNEL_SWAP_GIB`; si no están definidas, usa `"ubuntu-24.04"` y `32`, respectivamente. Los demás cambios no disparan automáticamente una compilación completa.

## Recursos observados

El preflight registra RAM disponible, límites y consumo de cgroup, swap utilizable y espacio real. Exige **36 GiB de RAM disponible + swap utilizable** y **45 GiB libres después de crear swap**. Es un margen basado en el enlace histórico cercano a 32 GiB; no garantiza que una nueva compilación termine. Los recursos y PSI se muestrean cada 15 segundos durante la compilación.

Solo en runners desechables administrados por GitHub se eliminan SDKs Android, .NET y GHC que esta receta no usa. Si hace falta y cabe sin consumir el margen de disco, se crea un archivo adicional de swap de hasta los GiB solicitados, conservando la swap existente. El archivo se desactiva y elimina al terminar. Los runners propios deben tener su swap ya configurada; el workflow no elimina sus SDKs ni modifica su swap.

Un runner estándar puede fallar este preflight o superar las seis horas disponibles. La swap puede hacer mucho más lento Full LTO. En ese caso se conservan los registros y debe seleccionarse un runner con más recursos. Un fallo de memoria, disco, compilación o auditoría impide publicar el kernel.

## Artefactos y publicación

Los artefactos de Actions se conservan 90 días y requieren acceso al repositorio privado. También se conservan registros cuando falla una compilación. La publicación usa un job separado con permiso `contents: write`; el contenedor de compilación no recibe un token de GitHub.

Cuando `publish` está activado, la entrega se carga como borrador de una prerelease experimental con una etiqueta nueva que incluye versión, commit y número de ejecución. Antes de publicarla, el workflow descarga **todos** los archivos desde GitHub, comprueba sus SHA-256 y compara el listado con el original. No reemplaza assets de otra entrega. Las fuentes comprimidas se almacenan como asset de la publicación y como artefacto de Actions, fuera del historial Git normal.

La compilación `0.1.0-rc3-rebuild1` es una reconstrucción nueva. El resultado no se identifica con el binario rc3 que quedó inaccesible. Una compilación y sus auditorías no certifican arranque, rendimiento, temperatura ni estabilidad en el teléfono.

## Resultado observado en esta sesión

El [build de la serie completa](https://github.com/elpapu-exe/Cloude/actions/runs/40628797721) falló en el preflight de capacidad, antes de compilar. El [inventario independiente](https://github.com/elpapu-exe/Cloude/actions/runs/40629147342) comprobó que el runner estándar tiene un único volumen raíz de 71,6 GiB, sin disco adicional en `/mnt`. Tras la limpieza inicial quedaron 28,32 GiB libres; no caben la swap necesaria y un espacio de construcción suficiente. El margen de 45 GiB es conservador y no representa un pico medido de la candidata.

La siguiente ejecución requiere un runner de mayor capacidad registrado/disponible en la cuenta. No hace falta reconectar GitHub. No se generó ni publicó un kernel en esos intentos.
