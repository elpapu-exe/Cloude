# SmartPack y persistencia de zRAM

El usuario confirma que configuró manualmente 3 GiB lógicos de zRAM con SmartPack y que el cambio desaparece tras reiniciar. El kernel rc5 y el módulo CPU dejan esa gestión en SmartPack/ROM. La capacidad lógica y la RAM física ocupada por datos comprimidos son magnitudes distintas.

## Opción existente en SmartPack

El código público de SmartPack Kernel Manager incluye **Aplicar al arrancar / Apply on boot** por categoría, incluida **Memoria virtual / Virtual memory**. Si aparece en tu versión, revisa los ajustes guardados de esa categoría y activa su aplicación al arrancar para reaplicar la configuración que ya utilizas. No hace falta activar las demás categorías para conservar zRAM. El nombre y ubicación pueden variar con la versión instalada, que todavía no identificamos.

La categoría abarca los ajustes de memoria guardados, no solo un valor aislado de zRAM. Su implementación de cambio de tamaño ejecuta swapoff, reset, tamaño nuevo, mkswap y swapon. Es una reconfiguración real del dispositivo de swap; no equivale a añadir RAM física ni demuestra que 3 GiB mejore este uso. Mantén un único gestor de zRAM y confirma después del reinicio el tamaño que realmente quedó activo. Una ROM puede volver a modificarlo.

## Prueba con pocos pasos

Compara con el mismo tamaño de zRAM, compresor y módulos necesarios. Deja estabilizar el arranque. Acción del módulo CPU recoge 180 segundos mientras usas TikTok y cambias entre las mismas aplicaciones; guarda el TXT de Descargas al aparecer TEST FINISHED. No cambia el perfil durante la captura.

Fuentes públicas revisadas:

- [Configuración de tamaño y guardado en la categoría VM](https://github.com/SmartPack/SmartPack-Kernel-Manager/blob/master/app/src/main/java/com/smartpack/kernelmanager/utils/kernel/vm/ZRAM.java).
- [Interruptor Aplicar al arrancar y categorías](https://github.com/SmartPack/SmartPack-Kernel-Manager/blob/master/app/src/main/java/com/smartpack/kernelmanager/fragments/ApplyOnBootFragment.java).
- [Servicio que reaplica ajustes guardados](https://github.com/SmartPack/SmartPack-Kernel-Manager/blob/master/app/src/main/java/com/smartpack/kernelmanager/services/boot/ApplyOnBoot.java).

La consulta de estas fuentes no certifica el comportamiento de otra versión o de una compilación modificada de SmartPack.
