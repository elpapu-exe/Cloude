# Estado y continuación

Actualización: 2026-10-23. Proyecto: **ChatGPT Kernel 0.1.0-rc1**, Redmi Note 12 4G topaz/tapas, LineageOS 20 Android 13.

## Terminado

- Fuentes R10 fijadas en `d246c8c17548bb1a2756092cabf34d11eedcde8c` y dependencias registradas en `config/sources.lock.json`.
- Toolchain Cirrus 24, SHA-256 y LLVM revision verificados.
- ReSukiSU histórico con historia Git completa: 4442 commits, versión 35142, identidad v4.2.0-rc1-7e92d45e. SUSFS 2.3.0 y BBG a54e0dc6 integrados.
- MGLRU activado por defecto; el usuario confirmó que estaba desactivado en su teléfono.
- Compilación completa con O2, Full LTO, CFI, BTF, protecciones térmicas y de módulos. Full LTO llegó cerca del límite de 32 GiB y terminó correctamente; no se cambió a ThinLTO.
- Primera interrupción por ausencia de cpio resuelta añadiendo herramientas Debian extraídas localmente, sin modificar el sistema.
- Cabeceras ARM64/ELF, release, identidades y configuración incorporada verificados.
- Los 15.543 exports y CRC coinciden con R10; no falta ninguno. Decoder contrastado contra vmlinux.symvers.
- Serie de tres parches repetida contra los archivos originales: 30 archivos finales idénticos. Checkpatch KProfiles sin errores/avisos.
- Instalador KSU-only boot/slot activo con respaldo obligatorio. Cuatro pruebas de copia y fallos pasadas; sintaxis BusyBox ash pasada.
- Investigación y límites en docs/, incluidos tres avisos BTF conocidos en release-notes.md.

## Entrega

- Imagen compilada: `out/arch/arm64/boot/Image`.
- Artefactos y fuentes preparados en `dist/` mediante `scripts/package-sources.sh`; checksums en `dist/SHA256SUMS` al concluir el empaquetado.
- Reconstrucción: docs/build.md. Instalación manual y recuperación: docs/installation.md.

## Pendiente en el teléfono

No hay acceso al dispositivo. No se ha flasheado ni se certifica arranque, módulos del vendor, root, TikTok, temperatura o batería. El instalador no debe presentarse como estable validado en hardware.

## Límites de la sesión

No se puede observar la cuota de Plus. Dos revisiones auxiliares recibieron un límite del servicio; el proceso principal continuó con compilación y comprobaciones locales. Este archivo conserva el punto de continuación.
