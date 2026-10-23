# Estado y continuación

Actualización: 2026-10-23. Proyecto solicitado: **ChatGPT Kernel** para topaz/tapas, manteniendo LineageOS 20 Android 13, KernelSU, WaEnhancer e InstaEclipse.

## Terminado

- Fuentes R10 fijadas en `d246c8c17548bb1a2756092cabf34d11eedcde8c`, descargadas en `.cache/linux`.
- Toolchain Cirrus 24 verificado con SHA-256 oficial; LLVM `c1100cd94…`.
- KernelSU histórico fijado en `7e92d45e…`; historia Git completa comprobada: 4442 commits, versión 35142, tag `v4.2.0-rc1`.
- Herramientas de host descargadas de Debian y extraídas localmente, sin instalar ni alterar el sistema; incluida `cpio`, cuya ausencia interrumpió el primer intento.
- Investigación de memoria, rendimiento y ABI en `docs/`.
- Confirmación del usuario: MGLRU actual desactivado (`0x0000`).
- Parche KProfiles revisado, compilado y validado con checkpatch: `patches/0003-kprofiles-fix-context-and-input.patch`.
- Serie de tres parches repetida contra los archivos originales: los 30 archivos finales coinciden.
- ReSukiSU y SUSFS ya compilados; log confirma versión 35142 / v4.2.0-rc1-7e92d45e / SUSFS 2.3.0.

## En curso

- Integración fijada de SUSFS 2.3.0 y Baseband Guard completa. BBG `a54e0dc6` coincide con la identidad incorporada en los binarios R10.
- Configuración efectiva verificada y compilación de una candidata en marcha (`logs/build.log`). No se realizará otra compilación completa de referencia en esta entrega.
- Instalador AnyKernel3 preparado con copia local previa del boot; cuatro pruebas de copia y fallos pasadas. Limitado a topaz/tapas Android 13, slot activo.

## Pendiente antes de entregar un ZIP

- Compilación correcta de la imagen, configuración efectiva, hashes y metadatos.
- Validación de formato ARM64, KSU, protecciones, símbolos/ABI y contenido del paquete.
- Documentación de recuperación y límites: **no hay prueba de arranque ni rendimiento en el teléfono**.
- El instalador no debe flashearse automáticamente ni presentarse como una versión estable validada.

## Decisiones

- Mantener frecuencias, voltajes, térmicas, CFI, MODVERSIONS y módulos del vendor.
- Habilitar MGLRU por defecto con TTL cero; no imponer nuevos umbrales LMKD ni tamaño/algoritmo zRAM desde el kernel.
- No prometer equivalencia binaria con R10: su receta usa dependencias móviles y una configuración IKCONFIG stock explícitamente incorporada desde `khaje-stock_defconfig`.
- Las pruebas finales de arranque y funciones del teléfono no pueden realizarse desde este entorno.
- No se puede observar la cuota de Plus. Dos revisiones auxiliares recibieron un límite del servicio; el proceso principal continuó con compilación y comprobaciones locales.
