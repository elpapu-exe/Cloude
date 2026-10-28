# Instalación y recuperación

**ChatGPT Kernel 0.1.0-rc4** es una candidata experimental para Redmi Note 12 **4G TAPAS/topaz y Android 13**, con la LineageOS 20 del usuario como referencia. **Compilada y publicada:** [ZIP y hashes verificados](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783). Todavía no se ha probado en el teléfono. No corresponde al Redmi Note 12 5G. Compilar y comprobar exports/CRC no certifica arranque, módulos del vendor o estabilidad.

La [publicación anterior rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) permanece disponible con sus propios hashes e instrucciones. Es una reconstrucción distinta del rc3 histórico inaccesible; su ZIP no debe identificarse como rc4. Para otras ROM A13, la compatibilidad del dispositivo, ramdisk y módulos requiere comprobación real.

El ZIP conserva KernelSU/ReSukiSU y sus mecanismos de módulos. Mantén la ROM y los módulos que necesitas; el paquete no incluye tus módulos personales ni configura sus ámbitos. Cada integración requiere comprobación real después del arranque. Conserva las protecciones térmicas; Kreapic Thermal Disabler debe seguir retirado.

## Copia previa fuera del teléfono

Guarda una copia verificada del **boot completo del slot activo antes de instalar**. El respaldo que hace el instalador es adicional: si Android no inicia, quizá no puedas acceder al almacenamiento cifrado donde lo guarda.

1. Descarga [chatgpt-backup-current.sh](../downloads/chatgpt-backup-current.sh) en **Descargas**, desbloquea el teléfono y ejecuta en Termux:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-backup-current.sh'
```

El script comprueba root, dispositivo y propiedades del slot; lee únicamente `boot_a` o `boot_b`. Crea un directorio nuevo `Download/ChatGPTKernel-backups/manual-<fecha><slot>-<id>/`, compara el tamaño con la partición y verifica su SHA256. No flashea, cambia de slot ni transmite archivos. Espera `VERIFIED`; un directorio incompleto o con `.partial` no sirve como respaldo verificado. No se reutiliza ni sobrescribe un respaldo anterior.

2. Copia **todo ese directorio** al ordenador u otro almacenamiento externo. Guarda juntos `boot.img`, `SHA256SUMS` y `backup-info.txt`. Anota el `Slot` registrado y comprueba el hash de la copia. En PowerShell, dentro del directorio copiado:

```powershell
(Get-FileHash .\boot.img -Algorithm SHA256).Hash.ToLower()
Get-Content .\SHA256SUMS
Get-Content .\backup-info.txt
```

El hash de la primera orden debe coincidir exactamente con los 64 caracteres de `SHA256SUMS`. En Linux puede usarse `sha256sum -c SHA256SUMS`. Conserva también el ZIP **R10 KSU** que ya funcionaba y las herramientas/recovery de recuperación habituales.

3. Verifica el ZIP nuevo contra el `SHA256SUMS` de su entrega. Conserva los ajustes y módulos necesarios. No añadas perfiles nuevos de CPU, memoria o zRAM para la primera comparación. Esta entrega no instala un servicio que fuerce esos valores al arrancar.

No continúes si el respaldo no se verificó fuera del teléfono o no dispones de un método conocido para restaurar `boot`.

## Instalación

Instala el ZIP AnyKernel3 desde un recovery compatible y con almacenamiento descifrado. El paquete sustituye únicamente el kernel del **boot del slot activo**, conservando su ramdisk. No incluye DTB, DTBO, `vendor_boot`, `init_boot` ni módulos del vendor. No cambies de slot durante este proceso.

Antes de escribir, el instalador guarda además el boot completo y sus metadatos en `Download/ChatGPTKernel-backups/<fecha><slot>-<id>/`. Si no puede guardar y verificar esa copia, aborta; no elimines esa comprobación. Reinicia después de instalar.

## Comprobación tras arrancar

En Termux:

```sh
uname -r
su -c 'cat /sys/kernel/mm/lru_gen/enabled'
```

Si instalaste rc4, se espera `5.15.216-ChatGPTKernel-0.1.0-rc4`. Si elegiste la entrega anterior rc3-rebuild1, su nombre seguirá siendo `5.15.216-ChatGPTKernel-0.1.0-rc3-rebuild1`. En MGLRU debe estar activo el bit 0: valores como `0x0001`, `0x0003` o `0x0007` lo indican; los bits adicionales dependen de las capacidades ARM. La ROM o un módulo pueden modificar parámetros después del arranque. rc4 restaura `watermark_scale_factor=10` como inicializador; la entrega anterior usaba 64. No instales un script para forzarlo durante la primera comparación.

Comprueba KernelSU, módulos necesarios, llamadas/datos, Wi-Fi, cámara, suspensión, carga y notificaciones de WhatsApp. Después realiza [la prueba de cinco minutos](testing.md). Si falla alguna función básica o hay reinicios, restaura el boot anterior. No se ha demostrado que esta candidata reduzca ANR, temperatura o tirones.

## Recuperación si no inicia

Entra al recovery/fastboot mediante el procedimiento habitual del dispositivo. Puedes reinstalar desde recovery el ZIP **R10 KSU** que ya funcionaba o restaurar tu `boot.img` completo verificado en la **misma partición y slot registrados** en `backup-info.txt`.

Desde el ordenador, confirma primero el slot actual:

```sh
fastboot getvar current-slot
```

Si el respaldo indica `Slot: _a` y fastboot confirma `a`, restaura:

```sh
fastboot flash boot_a boot.img
fastboot reboot
```

Para un respaldo `Slot: _b` con fastboot confirmando `b`:

```sh
fastboot flash boot_b boot.img
fastboot reboot
```

Usa `boot.img` de tu copia verificada y correspondiente a esta ROM. Si el slot actual no coincide con el respaldo, detente y revisa qué cambió antes de escribir. No cambies el slot ni flashees otras particiones para probar esta entrega. Restaurar boot conserva los datos y la ROM; la compatibilidad de los módulos sigue dependiendo de su instalación original.
