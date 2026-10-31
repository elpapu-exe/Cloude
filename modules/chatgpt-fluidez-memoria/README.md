# ChatGPT Fluidez Memoria

Módulo KernelSU/ReSukiSU de scripts, para TAPAS/topaz Android 13 y kernel 5.15 ARM64. Prueba dos controles de memoria de forma finita y reversible: habilitar el core MGLRU si estaba apagado y elevar `watermark_scale_factor` a 64 si era menor. No hay una mejora de rendimiento demostrada en el teléfono. No se necesita recompilar ni flashear el kernel.

Las instrucciones que permanecen instaladas son [INSTRUCCIONES.txt](INSTRUCCIONES.txt). El KernelSU histórico elimina README.md al instalar. `skip_mount` y la ausencia de `system/`, `system.prop` y `sepolicy.rule` evitan depender de montajes, metamódulos o modificaciones de SELinux.

El estado se guarda fuera de MODDIR para conservar el original al actualizar. Cada arranque usa un `boot_id`; una restauración antigua nunca se aplica al siguiente. Se mantiene un journal antes de escribir, se verifica lectura posterior y se conservan los errores. Los cambios de otros controladores se respetan cuando difieren del valor aplicado. No hay un CAS atómico procfs/sysfs ni garantía de recuperar el historial anterior de memoria.

Referencias primarias:

- [MGLRU: kill switch y cambios en ejecución](https://kernel.org/doc/html/v6.1/admin-guide/mm/multigen_lru.html). Se usa el bit principal, conservando los demás.
- [VM sysctl 5.15: watermarks y direct reclaim](https://kernel.org/doc/html/v5.15/admin-guide/sysctl/vm.html). La elección experimental de 64 procede de este proyecto; upstream no prescribe ese valor.
- [KernelSU: guía de módulos](https://kernelsu.org/guide/module.html). La compatibilidad de scripts/Acción se contrastó también con la fuente histórica fijada en este repositorio (`kernel-source/kernelsu/userspace/ksud/src/android/`). El versionCode del kernel no identifica por sí solo el Manager/ksud instalado.

No se modifica zRAM, LMKD, CPU/GPU, térmicas o módulos personales. `page-cluster` se conserva: el swap-in síncrono habitual de zRAM con una referencia ya evita readahead en la base, por lo que añadir ese ajuste no asegura un beneficio. La aplicación solo ocurre tras el arranque completo o por acción explícita; no hay bucle de imposición.

Pruebas: `python3 -m unittest discover -s tests -p 'test_fluidez_module.py'`. Empaquetado reproducible: `python3 scripts/package-fluidez-module.py`. Publicación separada del kernel en `.github/workflows/fluidez-module.yml`; sus fuentes, registro, manifest y SHA256SUMS acompañan el ZIP. Las pruebas de fixtures no validan el arranque ni la fluidez del teléfono.
