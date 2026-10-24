# Prueba temporal: 2 + 1 GiB de zRAM

Este ensayo está dirigido al Redmi Note 12 4G `tapas` con Android 13 y KernelSU. Añade un dispositivo zRAM nuevo de **1 GiB de capacidad lógica** al dispositivo activo de 2 GiB. Conserva el compresor y la prioridad de este último. La memoria física adicional depende de cuánto se utilice y de la compresión; no se reservan 1 GiB físicos al aplicar el ensayo.

El registro que motivó la prueba mostró zRAM llena, pausas de memoria y una terminación LMKD por swap agotada y thrashing. La capacidad adicional podría ayudar a esa situación, pero también puede aumentar el consumo de RAM física y el trabajo de compresión. No es una mejora de rendimiento demostrada ni una corrección de todos los fallos de TikTok o Instagram.

## Aplicación

1. Descarga [chatgpt-zram-prueba.zip](../downloads/chatgpt-zram-prueba.zip).
2. Extrae sus dos archivos `.sh` directamente en Descargas con el gestor de archivos. Es un archivo para extraer, no un módulo para flashear.
3. Con el teléfono desenchufado, pega en Termux:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-zram-try.sh apply && /system/bin/sh /sdcard/Download/chatgpt-fluidez-zram.sh 120'
```

4. Si el ensayo se aplica correctamente, el recolector comienza. Usa las mismas aplicaciones normalmente durante unos dos minutos, sin intentar saturarlas. Al terminar, comparte únicamente el archivo `ChatGPTKernel-<fecha>-<id>.txt` que indica el recolector. El informe adicional `ChatGPTKernel-zRAM-...txt` es el estado de aplicación de la prueba; puede servir si hay un error.

La comprobación útil es si disminuyen los tirones y la presión de memoria sin empeorar el calor, el consumo o la retención de apps. Más swap disponible por sí sola no demuestra una mejora. El recolector v4 registra todos los dispositivos zRAM y los contadores globales; algunos resúmenes de Android pueden seguir mostrando solo el dispositivo original.

## Comprobaciones y retirada

El script exige root, `tapas`, API 33, un único dispositivo de swap activo que sea zRAM0 de 2 GiB, al menos 512 MiB de `MemAvailable` inicial y las herramientas BusyBox de KernelSU. Ese margen inicial no constituye una reserva de RAM. Si falta un requisito, aborta sin asignar un dispositivo nuevo.

Lee `hot_add` una sola vez después de validar los requisitos: esa lectura crea el dispositivo. Comprueba su identidad de bloque y actúa solo sobre el dispositivo recién creado. No ejecuta `swapoff`, no reinicia zRAM0, no cierra aplicaciones y no modifica LMKD, CPU, voltajes, protecciones térmicas, ROM ni módulos LSPosed. En un fallo solo intenta retirar el dispositivo nuevo cuando puede demostrar que no está activo. Si su estado no es seguro, lo conserva hasta reiniciar.

**Para retirar la ampliación, reinicia el teléfono.** No instala un servicio de arranque ni vuelve a aplicarse automáticamente. El ensayo y su bloqueo no se duplican dentro del mismo arranque; sus archivos de diagnóstico/control no reactivan nada al reiniciar. No se ofrece una retirada mediante `swapoff` bajo carga.

Para generar un estado sin aplicar cambios:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-zram-try.sh status'
```

El código tiene pruebas con Android y BusyBox simulados. La disponibilidad de los controles sysfs, las políticas SELinux y la mejora real deben comprobarse en el teléfono.
