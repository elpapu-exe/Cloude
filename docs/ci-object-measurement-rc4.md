# Comprobación de objetos rc4

La recompilación **incremental** de `make -j2 descend` terminó sin errores en 42 segundos, reutilizando los objetos de rc3-rebuild1. Recompiló los archivos modificados; no mide el tiempo de una compilación limpia ni ejecuta el enlace Full LTO local. La configuración efectiva difiere de rc3-rebuild1 solamente en LOCALVERSION. El código restaura el inicializador de watermark a 10 y añade los seis arreglos documentados.

Quedaron 2.985 objetos y 1.151.901.696 bytes asignados en `out`; `.cache` ocupa 2.143.612.928 bytes. El máximo muestreado de `memory.current` fue 4.216.295.424 bytes en el cgroup compartido: incluye caché y otros procesos, no es RSS exclusivo del compilador. Las muestras, hashes de configuración, lock y dieciséis parches se conservan en [el registro JSON](ci-object-measurement-rc4.json).

Se mantiene el perfil de runner que completó rc3-rebuild1 en [Actions 40633724058](https://github.com/elpapu-exe/Cloude/actions/runs/40633724058): memoria/swap disponible combinada mínima de 36 GiB, al menos 15 GiB libres después de provisionarla y guardia de disco de 2 GiB. Se vuelven a medir los recursos reales del runner; el éxito previo no garantiza futuras compilaciones. No se desactiva ninguna protección para reducir memoria.

La receta ejecuta una reconstrucción limpia en GitHub Actions, el enlace global y las auditorías finales antes de publicar. Su resultado y hashes definitivos deben leerse en el manifest de esa ejecución; esta comprobación local no valida el arranque ni rendimiento del teléfono.

## Resultado medido en Actions

[Run 40663572783](https://github.com/elpapu-exe/Cloude/actions/runs/40663572783) terminó correctamente. El runner tenía 2 CPU y 8.323.964.928 bytes de RAM; se añadieron 28 GiB de swap y el contenedor registró 40.381.706.240 bytes disponibles combinados al iniciar. La fase limpia de objetos tardó 19 min 33 s; Image/Full LTO, 1 h 16 min 10 s. GNU time registró 7.917.819 faltas mayores de página y 183.148.400 unidades de entrada de filesystem. El máximo RSS fue 7.237.892 KiB: mide memoria física residente, no la memoria virtual máxima ni todo el consumo de RAM más swap. El enlace terminó con mucha paginación/E/S; no se debe usar el tiempo de otro runner como garantía. Los registros de recursos y guardia de disco acompañan la publicación.
