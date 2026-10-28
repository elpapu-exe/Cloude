# Estado y continuación

Actualización: 2026-10-27 (America/La_Paz). Candidata **0.1.0-rc3-rebuild1**.

## Recuperación comprobada

El nuevo ejecutor responde y contiene `/workspace/Cloude`, inicialmente limpio en `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. GitHub confirma que `chatgpt-kernel-download` es la única rama y la predeterminada; `main` no existe. No había Releases ni ejecuciones de Actions. El binario disponible era rc1.

El commit local rc2 `b6107b63…`, rc3 sin commit, `dist/`, `logs/rc3-checkpoint.json` y los binarios con hashes históricos no están en este checkout. No se borró ni sobrescribió el entorno anterior. No hay un mecanismo disponible en este ejecutor para montar arbitrariamente su disco; su contenido no se declara perdido ni recuperado.

## Reconstrucción

Serie nueva de nueve parches reaplicada sin fuzz: 35 archivos modificados comprobados. Árboles completos idénticos por contenido/tipo/symlink: Linux 76.069, KSU 764 y BBG 21 entradas. Compilaron localmente los cinco objetos ARM64 modificados; la configuración efectiva solo cambia LOCALVERSION respecto a rc1.

Regresiones de adquisición de fuentes, copias de arranque, tunables/frecuencia Horizon, contabilidad MGLRU y seguridad/capacidad SSG. Los cambios están reconstruidos y revisados de nuevo; no equivalen a recuperar exactamente las modificaciones anteriores.

La adquisición usa commits Git originales y archivos codeload inmutables con SHA256 y recibos de procedencia. KSU requiere su historia real completa para obtener versión 35142; si solo se dispone de su archive, la preparación aborta sin fabricar historia Git.

## Compilación y entrega

La compilación ARM64 de esta reconstrucción está pendiente de Actions. La validación anterior de rc3 no se hereda: cabeceras, configuración embebida, inicializador ELF, exports/CRC y archivo final de fuentes deben pasar en esta ejecución.

El ejecutor local tiene límite cgroup de RAM de 8 GiB, sin swap y unos 30 GiB libres al inicio: no sirve para el enlace Full LTO histórico de aproximadamente 32 GiB. CI mide RAM/cgroup/swap y disco antes de construir; requiere al menos 36 GiB disponibles combinados y 45 GiB libres después de provisionar swap. Un runner estándar puede fallar esa condición. Se admiten runners de más capacidad sin relajar protecciones.

No se añaden tarballs grandes a Git. La publicación solo ocurre tras compilación, comprobaciones, archivo fuente auditado y descarga verificada de todos sus assets. Los errores conservan registros de Actions.

## Teléfono

Esta reconstrucción no se ha instalado ni probado. Mantener WhatsApp y módulos necesarios, térmicas activas y TikTok oficial. La [prueba de cinco minutos](docs/testing.md) produce un archivo para comparar ANR, PSI, zRAM y temperatura; no presupone una causa de los ANR.
