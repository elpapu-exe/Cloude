# Estado y continuación

Actualización: 2026-10-27 (America/La_Paz). Candidata **0.1.0-rc3-rebuild1**.

## Recuperación comprobada

El nuevo ejecutor responde y contiene `/workspace/Cloude`, inicialmente limpio en `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. GitHub confirma que `chatgpt-kernel-download` es la única rama y la predeterminada; `main` no existe. No había Releases ni ejecuciones de Actions. El binario disponible era rc1.

El commit local rc2 `b6107b63…`, rc3 sin commit, `dist/`, `logs/rc3-checkpoint.json` y los binarios con hashes históricos no están en este checkout. No se borró ni sobrescribió el entorno anterior. No hay un mecanismo disponible en este ejecutor para montar arbitrariamente su disco; su contenido no se declara perdido ni recuperado.

## Reconstrucción

Serie nueva de nueve parches reaplicada sin fuzz: 35 archivos modificados comprobados. Árboles completos idénticos por contenido/tipo/symlink: Linux 76.069, KSU 764 y BBG 21 entradas. Compilaron localmente los cinco objetos ARM64 modificados y después terminó la fase `descend` con 2.985 objetos; la configuración efectiva solo cambia LOCALVERSION respecto a rc1.

Regresiones de adquisición de fuentes, copias de arranque, tunables/frecuencia Horizon, contabilidad MGLRU y seguridad/capacidad SSG. Los cambios están reconstruidos y revisados de nuevo; no equivalen a recuperar exactamente las modificaciones anteriores.

La adquisición usa commits Git originales y archivos codeload inmutables con SHA256 y recibos de procedencia. KSU requiere su historia real completa para obtener versión 35142; si solo se dispone de su archive, la preparación aborta sin fabricar historia Git.

## Compilación y entrega

La primera ejecución de la serie completa [40628797721](https://github.com/elpapu-exe/Cloude/actions/runs/40628797721) falló en el preflight; no compiló ni publicó kernel. El [inventario](https://github.com/elpapu-exe/Cloude/actions/runs/40629147342) confirmó un único volumen de 71,6 GiB y 7,75 GiB de RAM en el runner privado. El contrato de 32 GiB extra de swap más 45 GiB libres no cabía; 45 GiB era un margen conservador, no el pico medido del proyecto.

Se continuó midiendo el trabajo real, en vez de exigir al usuario que configure un servidor: `descend -j2` terminó con código 0 en 883 segundos, con 2.985 objetos y `out/` de 1,073 GiB; entradas de 1,996 GiB. [Medición y límites](docs/ci-object-measurement.md). El enlace Full LTO todavía no se intentó en esa medición.

La receta permite ahora un ensayo compacto en el runner estándar: checkout parcial, pruebas sobre la fuente realmente compilada, limpieza acotada a SDKs innecesarios del runner desechable y swap automática. El plan apunta a 37 GiB combinados incluyendo arranque, exige 36 GiB utilizables y reserva 15 GiB de trabajo tras swap. Vigila una reserva de 2 GiB durante objetos/enlace. Los ELF con DWARF no están medidos; no se garantiza éxito. Los runners propios no reciben limpieza/swap y conservan el margen de 45 GiB. No hay cambios de configuración de seguridad del kernel.

Se publicaron las 50 pruebas obligatorias, incluidas ocho de planificación/guardas; cuatro pruebas del recolector también pasan. Solo una compilación completa que verifique ARM64, configuración real, inicializador ELF, ABI, tar final y SHA256SUMS podrá publicar el ZIP. La publicación vuelve a descargar todos los assets para comprobarlos. Fuentes grandes y logs van a artefactos/Release, fuera del Git normal.

Terminados: reconstrucción y revisión, serie/árboles comprobados, fase de objetos, pruebas, receta, respaldo y guías. Pendientes: enlace completo, verificaciones de imagen/ABI, tar final auditado, Release y descarga nueva. El rc3 histórico y su tar no se recuperaron.

## Teléfono

Esta reconstrucción no se ha instalado ni probado. Mantener WhatsApp y módulos necesarios, térmicas activas y TikTok oficial. La [prueba de cinco minutos](docs/testing.md) produce un archivo para comparar ANR, PSI, zRAM y temperatura; no presupone una causa de los ANR.
