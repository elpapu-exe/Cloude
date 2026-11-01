# Investigación rc4: serialización de límites al iniciar el gobernador

Se adapta una corrección pequeña de concurrencia a schedutil y Horizon. No se
cambian el gobernador predeterminado, las frecuencias, los voltajes, los valores
de los tunables ni las protecciones térmicas y de seguridad.

## Evidencia y aplicación a estas fuentes

La corrección upstream [ce390caf5541c493c9061e7a2d98a463e66b736a](https://github.com/torvalds/linux/commit/ce390caf5541c493c9061e7a2d98a463e66b736a),
«cpufreq: schedutil: Serialize sugov_start() against rate limit updates», fue
integrada el 14 de octubre de 2026. Describe una carrera entre `sugov_start()` y
una escritura de `rate_limit_us`: el inicio puede leer el valor antiguo,
intercalarse con la escritura sysfs que publica el nuevo valor y su demora, y
finalmente sobrescribir esa demora con la calculada a partir del valor antiguo.
La demora queda desactualizada hasta una escritura posterior.

La base R10 conserva esa lectura y asignación sin el mutex de los atributos.
`governor_store()` en `drivers/cpufreq/cpufreq_governor_attr_set.c` ya mantiene
`attr_set.update_lock` al llamar a los métodos `*_store()`. El parche 0013 usa
ese mismo mutex alrededor de la lectura y asignación en `sugov_start()`.
La adaptación usa `mutex_lock()` y `mutex_unlock()` disponibles en Linux 5.15,
sin introducir el `guard()` de kernels más recientes.

Horizon contiene dos tunables de demora y presenta el mismo contrato. Su
bloqueo privado de tablas introducido en 0005 protege las tablas dinámicas,
pero no estas lecturas de tasas al arrancar. En Horizon, 0013 mantiene el orden
`attr_set.update_lock` → `min_rate_lock`, que ya utilizan los métodos sysfs, y
calcula el mínimo dentro de esa sección. No hay cambios de estructuras ni de
símbolos exportados.

La corrección actúa cuando el inicio del gobernador, por ejemplo durante un
reinicio o un cambio de estado de CPU, coincide con una escritura sysfs de la
tasa. No se ha demostrado que esta carrera ocurriera en el teléfono ni que
explique los tirones o ANR de TikTok.

## Pruebas reproducibles

Ejecutar:

```sh
python3 tests/test_cpufreq_start_serialization.py
```

Las cuatro pruebas compilan helpers reales extraídos de las fuentes con
ASan/UBSan y mutex de pthread. Solamente se instrumentan las cargas de los
tunables para seleccionar de forma determinista una intercalación posible.
Las escrituras, asignaciones, bloqueos y desbloqueos proceden de los helpers
reales. Los fixtures congelados conservan los helpers anteriores de
rc3-rebuild1 como controles negativos.

- Schedutil: una escritura concurrente de 1000 a 2000 µs debe dejar una demora
  efectiva de 2000000 ns. El control anterior termina con 1000000 ns y falla.
- Horizon: el mismo contrato se verifica por separado para las demoras de
  subida y bajada, además de su mínimo. Ambos controles anteriores fallan.
- Valores normales: 0, 1, 500 y UINT_MAX conservan la conversión y los valores
  esperados en ambos gobernadores.
- Progreso: 4000 inicios concurrentes con 4000 escrituras verifican que los
  bloqueos terminan, con tiempo máximo por proceso y comprobación del orden
  de adquisición. Horizon realiza dos escrituras por vuelta.

Son pruebas de helpers en el host, no una prueba de estrés del planificador
real ni una medida de fluidez del dispositivo. Mantener la comprobación de
exports/CRC y la prueba corta de logs del teléfono antes de atribuir mejoras.

## Cambios examinados que no se importan

- WALT e input-boost: `CONFIG_SCHED_WALT` está desactivado en la configuración
  del Image GKI. Eso excluye WALT de ese Image, pero **no demuestra que esté
  inactivo en el teléfono**: el vendor puede cargarlo como módulo. La receta
  `arch/arm64/configs/vendor/topaz_GKI.config` establece `CONFIG_SCHED_WALT=m`
  y `modules.list.msm.topaz` incluye `sched-walt.ko`. El gobernador `walt`
  apareció seleccionado en una captura posterior de rc4. Recompilar solamente
  el Image no actualiza ese módulo vendor conservado por el instalador.
- [3bff8f8e95fd](https://github.com/torvalds/linux/commit/3bff8f8e95fdc6ad19c8a1a8f87029094747e4bf),
  overflow de conversión de `rate_limit_us`: afecta a aritmética de 32 bits;
  esta compilación ARM64 utiliza `NSEC_PER_USEC` de tipo long de 64 bits.
- [f0a3f042293a](https://github.com/torvalds/linux/commit/f0a3f042293a8c5a2152346b3637ea60866c503a),
  publicación de hooks antes de inicializar todas las CPU: la base ya conserva
  las dos fases de inicialización y publicación.
- [9ef450ca74e4](https://github.com/torvalds/linux/commit/9ef450ca74e43dacf9a2a15db7a851052c78dcf0),
  estado pendiente en `adjust_perf`: el driver Qualcomm examinado no ofrece
  ese callback y la base tampoco tiene todas las condiciones que motivan el
  arreglo moderno. No justifica añadirlo para este dispositivo.

La investigación se limita a fuentes primarias y a los caminos presentes en
esta configuración; no constituye una revisión de todas las ramas comunitarias.

## Corrección a partir de la observación en ejecución

La captura identifica rc4 y muestra `walt` en ambas políticas. La conclusión anterior de inactividad basada solo en la configuración GKI era demasiado amplia. `walt.c` registra hooks y llama a `waltgov_register()`; `cpufreq_walt.c` registra el gobernador mediante `cpufreq_register_governor`, que exporta GKI. El módulo binario exacto todavía no se ha identificado. Mientras esté seleccionado WALT, los cambios específicos de schedutil/Horizon no controlan esas políticas; las correcciones comunes de memoria/Binder/F2FS siguen siendo independientes. No se debe habilitar otro WALT en el Image ni modificar módulos vendor sin revisar su receta, identidad y ABI.
