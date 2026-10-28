# Compilar y entregar con GitHub Actions

La candidata actual es **0.1.0-rc3-rebuild1**, una reconstrucción nueva. No corresponde al ZIP rc3 histórico con SHA `6c1cb3d1…`. Se conserva Full LTO, O2, CFI, Shadow Call Stack, BTF y MODVERSIONS. No hace falta compilar en Windows.

El workflow `.github/workflows/kernel.yml` se puede iniciar en Actions mediante **Run workflow** en `chatgpt-kernel-download`. También se ejecuta al cambiar `.github/build-request.json` en esa rama, para permitir entregas trazables desde Git.

## Recursos

El enlace anterior registró alrededor de 32 GiB temporales; no es el tamaño del ZIP. Se conserva Full LTO y su configuración de seguridad. La nueva medición de objetos (`descend -j2`, sin enlace) terminó con 2.985 `.o`, `out/` de 1,073 GiB y entradas de 1,996 GiB. Los ELF finales aún no se han medido: [presupuesto detallado](ci-object-measurement.md).

El perfil compacto para runners desechables de GitHub es un ensayo vigilado: recupera SDKs ajenos al build, evita fuentes duplicadas, calcula swap para 37 GiB combinados disponibles con margen de arranque y exige 36 GiB utilizables y 15 GiB libres de trabajo tras provisionarla. Conserva una vigilancia de 2 GiB de disco durante objetos/enlace. Esos umbrales son un presupuesto elegido con mediciones parciales y no garantizan que termine. El margen anterior de 45 GiB era conservador, no un requisito medido del kernel.

En self-hosted se mantiene el margen de disco de 45 GiB, sin limpiar SDKs ni crear swap. Se prefiere mayor RAM física cuando exista un runner adecuado, pero no se presupone su disponibilidad ni se contrata uno. [Uso y fases de Actions](build-actions.md).

## Receta

CI usa una imagen Debian 13 fijada por digest y las herramientas registradas. Descarga entradas verificadas, comprueba la historia original de KSU y reaplica los nueve parches sin fuzz. Los recibos distinguen Git real de archivos codeload; SUSFS continúa siendo un candidato de procedencia expresamente limitada.

```sh
python3 scripts/fetch_host_tools.py
python3 scripts/fetch-sources.py
python3 scripts/prepare-sources.py
bash scripts/configure.sh
bash scripts/build.sh 2>&1 | tee logs/build.log
python3 scripts/verify-artifact.py
python3 scripts/compare-r10-exports.py
bash scripts/package-sources.sh
python3 scripts/ci-audit-dist.py
```

Para reproducir fuera de CI se necesita Bash con `set -o pipefail`, los recursos anteriores y dependencias de `scripts/ci-build-in-container.sh`; consultar ese script para la receta completa. `CHATGPT_JOBS` controla paralelismo. Timestamp fijado en época `1793059200`; las dependencias del sistema del contenedor se registran. Una receta fijada no promete identidad binaria entre máquinas.

## Comprobaciones obligatorias

- Configuración de seguridad y compatibilidad, ARM64/ELF AArch64, versión/root, IKCONFIG idéntica a `.config` e inicializador `watermark_scale_factor=64` en ELF.
- Decoder de exports contrastado contra `vmlinux.symvers`, igualdad completa de símbolos y CRC con el R10 de referencia.
- Nueve suites (incluidos respaldo manual y controles de recursos CI) de regresión obligatorias: ausencia, fallo u omisión bloquean el empaquetado.
- Reaplicación de todos los parches y auditoría del archivo `.tar.zst` **final**, comparando cada contenido, tipo, modo y destino literal de symlink. Se excluyen `.git`, herramientas y objetos compilados.
- CRC e imagen/config del ZIP y listado cerrado SHA256SUMS.

`check-patches.py --compare-tracked` permite además contrastar todos los árboles preparados contra `kernel-source/`, ignorando diferencias de permisos entre el snapshot y Git. Los archives fuente se conservan como assets y artefactos de Actions, nunca en el historial Git normal.

El job de publicación usa permisos de escritura solo tras el build auditado. Crea un prerelease borrador con tag único, carga los archivos, vuelve a descargarlos y verifica todos sus hashes antes de hacerlo visible. Los artefactos y logs de Actions se retienen 90 días; los assets de Release no dependen de esa caducidad. Un fallo deja el kernel sin publicar y registros para diagnosticarlo.

El archivo de fuentes contiene los árboles completos preparados y los pines, pero excluye la historia `.git`. Para reconstruir, se obtiene de nuevo la historia original fijada de KSU y una base Linux limpia mediante esta receta en un checkout nuevo del commit de entrega. No se afirma que el tar pueda compilar sin red por sí solo.
