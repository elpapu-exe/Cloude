# Instalación y recuperación

Esta versión experimental está destinada a Redmi Note 12 **4G** topaz/tapas con la LineageOS 20 Android 13 del usuario y un arranque actualmente funcional con Zepharo R10. No corresponde al Redmi Note 12 5G. La compilación y las validaciones estáticas no certifican que arranque con todos los módulos del vendor.

El ZIP conserva KernelSU/ReSukiSU y sus mecanismos de módulos. No incluye tus módulos personales ni modifica sus ajustes. Conservar la integración no demuestra que cada módulo funcione correctamente con la nueva imagen. No se necesita entregar previamente el boot de la ROM.

## Antes de instalar

1. Guarda fuera del teléfono una copia del boot actual o el ZIP R10 que ya te funciona y ten disponible tu recovery/fastboot de recuperación. El respaldo automático del instalador es una protección adicional: si Android no arranca, quizá necesites un recovery que descifre el almacenamiento para recuperarlo.
2. Desactiva en FKM/SmartPack los perfiles personalizados de CPU, zRAM y memoria que se apliquen al iniciar. Conserva las protecciones térmicas; Kreapic Thermal Disabler debe seguir retirado. Mantén los módulos que necesitas.
3. Verifica el ZIP con el archivo SHA256SUMS de esta entrega. No instales sobre otro dispositivo o versión de Android.

## Instalación manual

Instala el ZIP AnyKernel3 mediante un recovery compatible y con el almacenamiento descifrado. El paquete está preparado para sustituir únicamente el kernel del **boot del slot activo**, conservando su ramdisk. No incluye DTB, DTBO, vendor_boot ni módulos del vendor.

Antes de escribir, guarda el boot completo con checksum y metadatos en:

`Download/ChatGPTKernel-backups/<fecha><slot>-<id>/`

Si no puede guardar y verificar esa copia, aborta. No fuerces ni elimines esa comprobación. Reinicia para usar el kernel; no puede cambiarse el kernel en ejecución sin reiniciar.

## Comprobación breve tras arrancar

En Termux:

```sh
uname -r
su -c 'cat /sys/kernel/mm/lru_gen/enabled'
```

Se espera `5.15.216-ChatGPTKernel-0.1.0-rc1`. En MGLRU debe estar activo el bit 0: valores como `0x0001`, `0x0003` o `0x0007` lo indican; los bits adicionales dependen de las capacidades ARM. Un módulo o script que escriba `0` puede desactivarlo nuevamente.

Comprueba KernelSU y, antes de usarlo como kernel diario, llamadas/datos, Wi-Fi, cámara, suspensión y carga. Después utiliza TikTok normalmente. Si continúan los bloqueos, conserva el ANR para investigarlos; aumentar frecuencias no explica ni resuelve por sí solo la presión de memoria.

## Si no arranca o funciona peor

Reinstala desde recovery el ZIP **R10 KSU** que ya te funcionaba, o restaura el `boot.img` completo del respaldo en el mismo slot que aparece en `backup-info.txt`.

Si utilizas fastboot desde un ordenador, revisa primero el slot:

```sh
fastboot getvar current-slot
```

Para un respaldo identificado como `_a`, el comando de restauración es `fastboot flash boot_a boot.img`; para `_b`, `fastboot flash boot_b boot.img`. Usa tu propio respaldo verificado y después `fastboot reboot`. No cambies el slot ni flashes otras particiones para probar esta entrega.

Este ZIP no evita la limitación física de 4 GB de RAM ni garantiza eliminar todos los ANR. Los resultados de fluidez, temperatura y batería necesitan comparación real en el teléfono.
