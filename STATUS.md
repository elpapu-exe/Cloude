# Estado y continuación

Actualización: 2026-10-28 (America/La_Paz). Candidata **0.1.0-rc3-rebuild1**.

## Recuperación comprobada

El nuevo ejecutor responde y contiene `/workspace/Cloude`, inicialmente limpio en `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. GitHub confirma que `chatgpt-kernel-download` es la única rama y la predeterminada; `main` no existe. No había Releases ni ejecuciones de Actions. El binario disponible era rc1.

El commit local rc2 `b6107b63…`, rc3 sin commit, `dist/`, `logs/rc3-checkpoint.json` y los binarios con hashes históricos no están en este checkout. No se borró ni sobrescribió el entorno anterior. No hay un mecanismo disponible en este ejecutor para montar arbitrariamente su disco; su contenido no se declara perdido ni recuperado.

## Reconstrucción

Serie nueva de nueve parches reaplicada sin fuzz: 35 archivos modificados comprobados. Árboles completos idénticos por contenido/tipo/symlink: Linux 76.069, KSU 764 y BBG 21 entradas. Compilaron localmente los cinco objetos ARM64 modificados y después terminó la fase `descend` con 2.985 objetos; la configuración efectiva solo cambia LOCALVERSION respecto a rc1.

Regresiones de adquisición de fuentes, copias de arranque, tunables/frecuencia Horizon, contabilidad MGLRU y seguridad/capacidad SSG. Los cambios están reconstruidos y revisados de nuevo; no equivalen a recuperar exactamente las modificaciones anteriores.

La adquisición usa commits Git originales y archivos codeload inmutables con SHA256 y recibos de procedencia. KSU requiere su historia real completa para obtener versión 35142; si solo se dispone de su archive, la preparación aborta sin fabricar historia Git.

## Compilación y entrega terminadas

[Run 40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058): build y publicación **SUCCESS**. Commit compilado `a01d67ebe63f98a705c068ea735f9ae87848b35c`. [Release experimental](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058). ZIP instalable: 25,215,885 bytes; SHA256 `4ecb0febfb9a284c3b624bab7e404ccc205941c69bf3a275312407d1267c2d55`.

La imagen ARM64 tiene 47.454.720 bytes, SHA256 `861973441ccc44bc59201b08eff5cdb03b0f56d379f43e758b0cf6af64c9d0bb`. La configuración efectiva y la embebida coinciden con SHA256 `959f9931856597bc5219a68392c77334887315c8e53e30a039f52b82dfaa3cc7`. Inicializador watermark=64 verificado en ELF. Conserva O2/Full LTO, CFI, SCS, BTF, MODVERSIONS y protecciones térmicas.

Los 15.543 exports y todos sus CRC coinciden con R10; no hay añadidos ni ausentes. Pasaron 50 pruebas obligatorias, sin fallos ni omisiones. El tar final de fuentes auditó 76.972 entradas por contenido, tipo, modo y destino literal de symlink; las cuentas de componentes incluyen su directorio raíz. Fuentes: 195.312.956 bytes, SHA256 `b967e8a4b2d1936e68f35821c2a59ebb0501992e070046decb42dfafdc3b544d`. No se añadieron a Git normal.

La publicación cargó 35 assets como borrador, los volvió a descargar, verificó los 34 archivos de SHA256SUMS y comparó el propio listado antes de hacer visible la prerelease. No hay un enlace inventado ni un binario recuperado del entorno anterior.

Avisos BTF reales: `filp_close`, `should_failslab`, `vfs_getattr`. La reconstrucción cambia el aviso histórico `should_fail_alloc_page` por `should_failslab`; no se afirma que todas las funciones tengan BTF resuelto. Más evidencia y recursos observados en [ci-build-result.json](docs/ci-build-result.json).

El bloqueo inicial de disco se resolvió midiendo la fase de objetos y usando limpieza acotada a SDKs del runner desechable, checkout parcial y swap automática. La receta estándar funcionó en esta ejecución sin relajar la configuración del kernel. Los límites y el margen de 15 GiB son propios de esta carga medida; no garantizan cualquier otra compilación.

Terminados: reconstrucción, revisión, serie/árboles comprobados, compilación completa, pruebas, imagen/ABI, tar auditado, publicación y descarga comprobada, receta de Actions, respaldo y guías. Pendiente: prueba real de arranque, funciones básicas, fluidez, ANR y temperatura en TAPAS. El rc3 histórico no se recuperó; este resultado es una reconstrucción nueva.

## Teléfono

Esta reconstrucción no se ha instalado ni probado. Mantener WhatsApp y módulos necesarios, térmicas activas y TikTok oficial. La [prueba de cinco minutos](docs/testing.md) produce un archivo para comparar ANR, PSI, zRAM y temperatura; no presupone una causa de los ANR.
