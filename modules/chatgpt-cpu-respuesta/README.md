# ChatGPT CPU Respuesta v0.1.0-rc1

Módulo KernelSU independiente para TAPAS/topaz con Android 13 y kernel 5.15 ARM64.
Su único ajuste posible es reducir un 25% `up_rate_limit_us` de WALT cuando el
valor leído está entre 20001 y 100000 µs. El objetivo se calcula mediante
`(original * 3 + 3) / 4`, redondeando hacia arriba. No cambia tasas menores ni
mayores a ese intervalo. En particular, 500–2000 µs produce una operación nula.
Es una heurística experimental de latencia, no una optimización medida en este
móvil. Permitir subidas más frecuentes puede aumentar consumo.

La semántica se revisó en
[`cpufreq_walt.c`](../../kernel-source/linux/kernel/sched/walt/cpufreq_walt.c):
`waltgov_up_down_rate_limit()` compara el tiempo desde el último cambio aceptado
con `up_rate_delay_ns`, y `up_rate_limit_us_store()` convierte µs a ns. Esta fuente
explica el contrato de referencia; no identifica por sí sola el binario vendor
cargado en el teléfono. El módulo comprueba interfaces y gobernador en runtime.

No cambia `down_rate_limit_us`, frecuencias, gobernador, voltajes, protecciones
térmicas, GPU, zRAM, MGLRU, watermark, LMKD, WhatsApp ni módulos personales.
No persiste la configuración manual de SmartPack ni activa el módulo de memoria.

## Uso

Instalar desde KernelSU y reiniciar. `service.sh` realiza una aplicación única,
con espera de arranque limitada. **Acción sólo inicia el recolector de 180 s**;
no cambia el estado del perfil. `bin/collect.sh` es una copia byte por byte del
recolector general del proyecto. Las instrucciones persistentes están en
[INSTRUCCIONES.txt](INSTRUCCIONES.txt), porque el instalador KernelSU puede retirar
README.md y customize.sh después de instalar.

La API CLI es `bin/control.sh apply|restore|status|report|toggle|boot|uninstall`.
`restore` pausa persistentemente el perfil y restaura sus cambios elegibles.
`apply` reactiva; `toggle` alterna sólo por CLI. Desactivar requiere reiniciar para
retirar los efectos sin usar `restore`.

## Plan y restauración

Sólo se escriben las rutas fijas `policy0/walt/up_rate_limit_us`,
`policy4/walt/up_rate_limit_us` o `walt/up_rate_limit_us` dentro de
`/sys/devices/system/cpu/cpufreq`. Los scopes global y por política contradictorios
se omiten. Cualquier directorio `policy*` distinto de `policy0`/`policy4` veta
aplicación y restauración. El global requiere que todas las políticas presentes y soportadas
estén en WALT. Las rutas compartidas se deduplican por identidad antes de escribir.

El plan completo captura todos los valores originales y objetivos antes de la
primera escritura. Cada escritura exige que el original siga vigente, guarda el
journal previamente y verifica lectura posterior. Una repetición no acumula
recortes. Los registros de formato 1, en
`/data/adb/chatgpt-cpu-respuesta/session/`, contienen nueve campos:

```
original objetivo canonical_node dev:inode participantes p0_canonical p0_dev:inode p4_canonical p4_dev:inode
```

`participantes` es `0`, `4` o `04`; campos no participantes usan `-`. Las rutas de
identidad almacenadas sólo se comparan y nunca seleccionan un destino de
escritura. La sesión se asocia a `boot_id`. Restaurar requiere ese mismo arranque,
identidades de nodo/políticas, gobernador WALT y lectura igual al objetivo propio.
Se preservan valores ajenos y registros no resueltos. Sysfs no ofrece CAS, así
que la comparación previa no elimina por completo carreras con otros procesos
root. No hay daemon de imposición ni montaje.

No se necesita APK, WebUI, motor de montaje ni reglas SELinux. La licencia del
módulo es GPL-2.0-only. Las verificaciones de código se reportan por separado;
no certifican una mejora de rendimiento en hardware.
