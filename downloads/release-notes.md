# ChatGPT Kernel 0.1.0-rc1

Compilación ARM64 realizada el 23 de octubre de 2026. Destino: Redmi Note 12 4G topaz/tapas, LineageOS 20 Android 13, conservando la base funcional Zepharo R10. **Candidata experimental; no probada en el teléfono.**

## Cambios propios

- MGLRU activo desde el arranque. El usuario confirmó que R10 lo tenía apagado (`0x0000`). TTL, zRAM y política LMKD no se modifican.
- KProfiles: validar entradas antes de tomar los locks; proteger estado coherentemente; ejecutar notificadores bloqueantes mediante trabajo diferido; retirar el cambio inseguro de schedulers de todos los discos. No se atribuye una mejora de fluidez medida a estas correcciones.
- IKCONFIG incorpora la configuración real que produjo el binario, sustituyendo la referencia stock fija de la fuente original.
- Instalador KSU-only, Android 13, slot activo, con respaldo completo del boot y checksum obligatorio antes de escribir.

Se conservan Clang/LLD 24, O2, Full LTO, CFI, MODVERSIONS, comprobaciones de módulos, frecuencias/voltajes y protecciones térmicas. HZ=300 corresponde al defconfig fijado; no se pudo recuperar cada entrada efectiva de la compilación histórica R10. ReSukiSU conserva versión 35142, identidad v4.2.0-rc1-7e92d45e y soporte de manager/módulos. SUSFS 2.3.0 está fijado a un candidato cronológico de su versión; Baseband Guard coincide con la revisión identificada en R10.

## Validación pasada

- Compilación completa `Image`, sin desactivar WERROR, CFI, BTF ni MODVERSIONS para completarla. Full LTO terminó dentro del límite de 32 GiB de RAM; no se usó el fallback ThinLTO.
- Cabecera ARM64 y ELF AArch64, release `5.15.216-ChatGPTKernel-0.1.0-rc1`, identidades KSU/SUSFS/BBG comprobadas.
- Configuración extraída de la imagen idéntica a la `.config` efectiva.
- **15.543 exports de R10 conservados, todos con CRC idénticos; cero ausentes, cero diferencias.** Los exports PREL32 y CRC se recuperaron del R10 publicado. El decodificador se contrastó con la imagen nueva y su `vmlinux.symvers`, obtenido de modpost.
- Tres parches repetidos desde los archivos originales: 30 archivos finales idénticos al árbol compilado. Checkpatch del parche KProfiles: cero avisos/errores.
- Cuatro pruebas del respaldo: copia correcta, tamaño incompleto, error de escritura y checksum incorrecto. Sintaxis de instalador comprobada también con BusyBox ash.

## Avisos y límites

El enlace terminó con tres avisos `resolve_btfids` para `dentry_open`, `vfs_getattr` y `should_fail_alloc_page`. Sus identificadores de función no están presentes en los metadatos BTF finales, lo que limita las rutas de trazado/BPF que requieren esos identificadores. No son exports ausentes ni CRC distintos. Se conservaron las opciones de generación BTF del árbol; una prueba aislada con menos opciones generó más avisos y no se incorporó al binario. El log y el manifiesto registran los tres avisos.

No se compararon los `.ko` reales del teléfono ni se probó su arranque, carga de drivers, root, módulos, TikTok, temperatura o batería. La coincidencia con los exports de R10 aporta evidencia de compatibilidad, sin certificar toda interacción semántica del vendor. No se promete eliminar todos los bloqueos con 4 GB de RAM.

El ZIP, manifiesto, configuración, informe ABI y fuentes se distribuyen con checksums. La guía de instalación incluye cómo recuperar el boot original. La nueva imagen requiere reiniciar para ejecutarse.
