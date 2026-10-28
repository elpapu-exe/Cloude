# ChatGPT Kernel 0.1.0-rc3-rebuild1

**Nueva reconstrucción experimental para TAPAS/topaz, Android 13 / LineageOS 20 del usuario.** No es el binario rc3 del entorno anterior. Compilación y validaciones de esta ejecución deben comprobarse en el manifest y los registros entregados. Sin prueba de arranque, estabilidad, fluidez, temperatura o batería en el teléfono.

Retiene MGLRU activo, IKCONFIG real, correcciones KProfiles e integración histórica ReSukiSU/SUSFS/BBG. Reconstruye el margen experimental de reclaim (`watermark_scale_factor=64`), protección de tablas de Horizon, reintentos de frecuencia/límites, contabilidad MGLRU por flags del CAS y correcciones de RCU/entrada/capacidad de SSG. Schedutil sigue por defecto; arreglos Horizon actúan al seleccionarlo.

No cambia tamaño/compresor zRAM, LMKD, swappiness, frecuencias, voltajes ni protecciones térmicas. La ROM puede sobrescribir el watermark al arrancar. Conservar CRC no demuestra estabilidad ni que todos los módulos del teléfono funcionen.

El SUSFS 2.3.0 fijado es un candidato cronológico, sin identificación demostrada de la fuente exacta de R10. No se afirma resolver todos los posibles problemas SSG, incluidos blkg retenidos y contabilidad multi-hctx. No se atribuyen los ANR del usuario a estas incidencias sin evidencia del dispositivo.

Las compilaciones históricas registraron avisos BTF para `filp_close`, `should_fail_alloc_page` y `vfs_getattr`. Los avisos efectivos de esta compilación se conservan en `build.log` y `build-manifest.json`; los anteriores no sustituyen una auditoría del nuevo resultado.

Antes de instalar: copia verificada del boot funcional fuera del teléfono, recovery/fastboot disponible y lectura de `LEEME-instalacion.md`. Conservar WhatsApp y módulos necesarios, térmicas activas y TikTok oficial. La comparación corta usa el recolector de solo lectura de `docs/testing.md`.

## Resultado publicado de esta reconstrucción

Actions 40633724058 completó la compilación y las auditorías desde a01d67ebe63f98a705c068ea735f9ae87848b35c. Pasaron 50 regresiones sin omisiones; 15.543 exports y CRC idénticos a R10; archivo final de fuentes auditado y todos los assets descargados y verificados antes de publicar. Los avisos BTF efectivos son `filp_close`, `should_failslab` y `vfs_getattr`: la lista histórica no identifica los avisos actuales. La validación en hardware sigue pendiente.
