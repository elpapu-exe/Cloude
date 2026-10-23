# Componentes y atribución

- Linux y cambios del árbol Zepharo: licencia y atribuciones en `.cache/linux/COPYING`, `LICENSES/` y los archivos fuente; commit y repositorio en `config/sources.lock.json`.
- ReSukiSU histórico, actualmente alojado en BakaSU: `.cache/kernelsu/LICENSE*` y sus encabezados originales.
- SUSFS: `.cache/susfs/README.md` y encabezados de los archivos copiados; revisión y hashes fijados.
- Baseband Guard: licencia y encabezados en `.cache/baseband-guard`; se conserva el commit identificado en R10.
- Instalador AnyKernel3: copyright osm0sis y colaboradores, licencia completa conservada en `installer/LICENSE` y en el ZIP de instalación.

El backend AnyKernel3 y sus herramientas binarias se toman del ZIP R10 verificado, ya usado como base por el dispositivo. No se presentan como herramientas compiladas en este proyecto. Ese ZIP y su digest están fijados en `config/sources.lock.json`; fuentes generales: [AnyKernel3](https://github.com/osm0sis/AnyKernel3), [Magisk/magiskboot](https://github.com/topjohnwu/Magisk) y [BusyBox](https://busybox.net/). La identidad exacta de cada revisión interna de esas herramientas no fue reconstruida.

El paquete de fuentes incluye el árbol del kernel, sus dependencias integradas, las modificaciones y los scripts de reconstrucción. El compilador y los paquetes de host se obtienen con hashes fijados y no se incluyen en ese archivo.
