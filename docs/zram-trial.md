# Prueba temporal: hasta 3 GiB lógicos de zRAM

Este ensayo está dirigido al Redmi Note 12 4G `tapas` con Android 13 y KernelSU. Añade un dispositivo zRAM nuevo con la capacidad que falte para alcanzar **3 GiB lógicos en total**, partiendo de una zRAM0 de al menos 2 GiB y menor de 3 GiB. El incremento nunca supera 1 GiB. Conserva el compresor original. Si la prioridad original es explícita y no negativa, la copia; si es automática y negativa, deja que el kernel asigne automáticamente al nuevo dispositivo una prioridad inferior, sin cambiar la original. La memoria física adicional depende de cuánto se utilice y de la compresión; no se reservan 1 GiB físicos al aplicar el ensayo.

El registro que motivó la prueba mostró zRAM llena, pausas de memoria y una terminación LMKD por swap agotada y thrashing. La capacidad adicional podría ayudar a esa situación, pero también puede aumentar el consumo de RAM física y el trabajo de compresión. No es una mejora de rendimiento demostrada ni una corrección de todos los fallos de TikTok o Instagram.

## Aplicación

1. Descarga [chatgpt-zram-prueba-v3.zip](../downloads/chatgpt-zram-prueba-v3.zip).
2. Extrae sus dos archivos `.sh` directamente en Descargas con el gestor de archivos. Es un archivo para extraer, no un módulo para flashear.
3. Con el teléfono desenchufado, pega en Termux:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-zram-try-v3.sh apply && /system/bin/sh /sdcard/Download/chatgpt-fluidez-zram.sh 120'
```

4. Si el ensayo se aplica correctamente, el recolector comienza. Usa las mismas aplicaciones normalmente durante unos dos minutos, sin intentar saturarlas. Al terminar, comparte únicamente el archivo `ChatGPTKernel-<fecha>-<id>.txt` que indica el recolector. El informe adicional `ChatGPTKernel-zRAM-...txt` es el estado de aplicación de la prueba; puede servir si hay un error.

La comprobación útil es si disminuyen los tirones y la presión de memoria sin empeorar el calor, el consumo o la retención de apps. Más swap disponible por sí sola no demuestra una mejora. El recolector v4 registra todos los dispositivos zRAM y los contadores globales; algunos resúmenes de Android pueden seguir mostrando solo el dispositivo original.

## Comprobaciones y retirada

El script exige root, `tapas`, API 33, un único dispositivo de swap activo que sea zRAM0 de al menos 2 GiB y menor de 3 GiB, con tamaño alineado a páginas de 4 KiB, al menos 512 MiB de `MemAvailable` inicial y las herramientas BusyBox de KernelSU. Ese margen inicial no constituye una reserva de RAM. Si falta un requisito, aborta sin asignar un dispositivo nuevo.

Lee `hot_add` una sola vez después de validar los requisitos: esa lectura crea el dispositivo. Comprueba su identidad de bloque y actúa solo sobre el dispositivo recién creado. No ejecuta `swapoff`, no reinicia zRAM0, no cierra aplicaciones y no modifica LMKD, CPU, voltajes, protecciones térmicas, ROM ni módulos LSPosed. En un fallo solo intenta retirar el dispositivo nuevo cuando puede demostrar que no está activo. Si su estado no es seguro, lo conserva hasta reiniciar.

**Para retirar la ampliación, reinicia el teléfono.** No instala un servicio de arranque ni vuelve a aplicarse automáticamente. El ensayo y su bloqueo no se duplican dentro del mismo arranque; sus archivos de diagnóstico/control no reactivan nada al reiniciar. No se ofrece una retirada mediante `swapoff` bajo carga.

Para generar un estado sin aplicar cambios:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-zram-try-v3.sh status'
```

El código tiene pruebas con Android y BusyBox simulados. La disponibilidad de los controles sysfs, las políticas SELinux y la mejora real deben comprobarse en el teléfono.

## Corrección de las escrituras en Android: versión 2

Los primeros informes del teléfono mostraron `printf: write: Invalid argument` al seleccionar el compresor y al retirar el dispositivo nuevo. Diez segundos después solo existía zRAM0 y no había swap adicional, pero seguía el bloqueo en estado `allocating` con ID 1. La prueba no llegó a activar la ampliación.

El [`printf` de Toybox en Android 13](https://github.com/aosp-mirror-neo/platform_external_toybox/blob/android-13.0.0_r1/toys/posix/printf.c) procesa los caracteres literales con `putchar`; su [salida se configura sin búfer](https://github.com/aosp-mirror-neo/platform_external_toybox/blob/android-13.0.0_r1/main.c). Escribir `printf '%s\n' valor` sobre sysfs puede enviar primero el valor y después un salto de línea separado. El controlador acepta el primero y rechaza el segundo. Un formato numérico literal también puede dividirse en varias escrituras.

La versión 2 usa una única conversión corta `printf '%s' "$valor"` sin caracteres adicionales para las tres escrituras sysfs. Si el nuevo dispositivo ya usa el compresor correcto, no lo vuelve a escribir. Antes de configurarlo exige tamaño cero e inactividad comprobada. Después de un fallo captura también el estado final y verifica que el dispositivo nuevo realmente desapareció antes de dar por terminada la limpieza.

Para el bloqueo dejado por el primer intento, solo archiva sus metadatos y continúa si corresponden al mismo arranque, el estado era `allocating`, el PID anterior ya no existe, el ID es válido, el dispositivo está ausente en ambas rutas sysfs y solo quedan zRAM0 y su swap. Si el dispositivo anterior todavía existe, está activo o cualquier comprobación es dudosa, conserva el bloqueo y aborta. No borra el bloqueo a ciegas ni intenta retirar un dispositivo de una ejecución anterior. La recuperación puede hacerse sin reiniciar cuando se cumplen todas las condiciones; no ofrece una garantía frente a otro controlador root que modifique zRAM simultáneamente.

Las ejecuciones `apply` de esta versión se serializan con un directorio adicional que permanece adquirido durante toda la operación, incluida la recuperación. Se libera al terminar o en una interrupción manejable. Si el proceso muere sin ejecutar su limpieza, ese directorio bloquea nuevos intentos hasta inspección o reinicio; no se toma por la fuerza. `status` sigue siendo de solo lectura.


## Tamaño existente y prioridad automática: versión 3

Un informe posterior mostró una configuración distinta de zRAM0: **2520 MiB** de capacidad lógica, ruta `/block/zram0` y prioridad automática `-2`. Solo seguía presente zRAM0; el bloqueo del primer intento continuaba en estado `allocating`. El informe demuestra el cambio de configuración, pero no identifica qué aplicación o servicio lo realizó.

La versión 3 reconoce el alias exacto `/block/zram0` que puede mostrar `/proc/swaps` según el espacio de montajes. Si la ruta existe, exige que su identidad de bloque coincida con sysfs. Si ese alias no está disponible desde la shell, comprueba un nodo canónico accesible de zRAM0. También exige tipo `partition`, tamaño de swap coherente con la capacidad y la cabecera de 4 KiB de este kernel, y vuelve a comprobar tamaño, fila de swap e identidad antes de asignar el dispositivo adicional.

Para una base de 2520 MiB añade **552 MiB** (578813952 bytes). Para una base de 2048 MiB añade 1024 MiB. Usa `awk` de BusyBox para comprobar y calcular los tamaños en bytes, porque la aritmética del `mksh` de Android es de 32 bits. Con prioridad negativa llama a `swapon` sin `-p`: el kernel elige una prioridad automática inferior, normalmente `-3` si la base era `-2`. El dispositivo original conserva tamaño, compresor y prioridad.

Si no puede recuperar el bloqueo anterior, el error incluye la comprobación concreta que lo impide. La corrección de compatibilidad y las pruebas simuladas no demuestran una mejora de rendimiento en el teléfono.
