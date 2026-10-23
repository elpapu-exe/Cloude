# Baseband Guard

Se conserva el componente ya presente en R10. No se añade como optimización.

- Repositorio: https://github.com/vc-teahouse/Baseband-guard
- Commit: `a54e0dc6cf0aff4dd87fec49644a02d2eb612905`.
- Identidad: las dos imágenes R10 contienen `a54e0dc6` y el enlace del repositorio; su Makefile genera ambos textos desde Git.
- Archivo fuente: SHA-256 `304fe409a90d2562dc839b6165995106d80e89479ec14a6956c3c0ec42f89f2b`.
- Integración manual con el LSM moderno ya presente en Linux 5.15; no se ejecuta su instalador remoto.
- Se conservan desactivadas las protecciones opcionales de escritura de boot/recovery para permitir recuperación.
