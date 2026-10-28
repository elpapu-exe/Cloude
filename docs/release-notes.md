# ChatGPT Kernel 0.1.0-rc4

Candidata experimental para Redmi Note 12 4G TAPAS/topaz y Android 13. Continúa la reconstrucción publicada rc3-rebuild1; no es el binario rc3 perdido. La validación de arranque y rendimiento en hardware sigue pendiente. No se garantiza compatibilidad con cualquier combinación de ROM/vendor por conservar el nombre del dispositivo.

Cambios respecto a rc3-rebuild1:

- MGLRU: evita un subdesbordamiento de contadores durante reintentos de reclaim que puede acabar en división por cero en vmpressure; omite VMA especiales durante lookaround.
- Binder: corrige un rechazo prematuro justo en el límite de cuota de transacciones asíncronas. La mayor parte del arreglo upstream ya estaba en la base; no se atribuye una gran ampliación de capacidad a esta línea.
- Schedutil y Horizon: serializa el arranque del gobernador con escrituras sysfs de sus límites temporales. No cambia sus valores ni el gobernador por defecto (schedutil).
- F2FS: propaga errores de writeback al colapsar un rango y rechaza movimientos sobre el mismo archivo que se solapan tras expandir longitud cero. Son correcciones de integridad, no resultados de FPS.
- Restaura `watermark_scale_factor=10`, valor original de la base, para abandonar el ajuste experimental 64 sin mediciones y preparar una candidata de alcance más general. La ROM puede sobrescribirlo después del arranque.

Las referencias primarias, pruebas y cambios descartados están en `COMMUNITY-REVIEW.md` y en las fuentes correspondientes. Las pruebas de helpers reales con ASan/UBSan detectan los casos reproducidos; no sustituyen el arranque ni miden TikTok.

Retiene MGLRU activo, IKCONFIG real, correcciones KProfiles, de Horizon y de SSG anteriores, y la integración histórica ReSukiSU/SUSFS/BBG. Mantiene O2, Full LTO, CFI, Shadow Call Stack, BTF, MODVERSIONS y las protecciones térmicas. No cambia frecuencias, voltajes, LMKD, swappiness ni tamaño/compresor de zRAM. El tamaño lógico de zRAM lo configura la ROM o un módulo.

SUSFS 2.3.0 sigue siendo un candidato de procedencia cronológica, sin identificación demostrada de la fuente exacta de R10. No se afirma resolver todos los problemas posibles de SSG (blkg retenidos o contabilidad multi-hctx), ni atribuir los ANR del usuario a estos defectos sin registros del dispositivo. Los avisos BTF efectivos quedan en `build.log` y `build-manifest.json`.

Antes de instalar, guarda una copia verificada del boot funcional fuera del teléfono y lee `LEEME-instalacion.md`. La prueba de `docs/testing.md` conserva WhatsApp, módulos, protecciones térmicas y TikTok oficial.
