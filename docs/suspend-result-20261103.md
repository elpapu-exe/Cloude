# Primer informe real de reposo en rc5

El informe termina con TEST FINISHED y contiene dos capturas del mismo arranque. Se identifican TAPAS, Android 13 y `5.15.216-ChatGPTKernel-0.1.0-rc5`. No se publica el TXT original, identificadores del arranque, PID/UID ni nombres de trabajos de aplicaciones.

## Resultado medido

| Medida | Resultado |
| --- | --- |
| Intervalo entre relojes de captura | 1303,09 s: 21 min 43 s |
| Suspensión por diferencia BOOTTIME/MONOTONIC | 757,35 s: 12 min 37 s, 58,1% del intervalo |
| Suspensión de SuspendInfo | 757326 ms, consistente con los relojes |
| Pantalla apagada, delta de batterystats | 1274,255 s: 21 min 14 s |
| Pantalla encendida, delta de batterystats | 28,787 s |
| Suspensión como fracción aproximada del tiempo con pantalla apagada | 59,4% |
| Batería al inicio/final | 40 → 37 °C; indicador 34 → 33% |
| Contadores de suspensión al inicio | 0 intentos, 0 éxitos, 0 fallos |
| Contadores al final | 179 intentos; 160 marcados exitosos, 19 fallos |

El teléfono sí suspendió y se enfrió durante esta prueba. No se reproduce un bloqueo completo de suspensión. Quedan despertares y tiempo despierto con pantalla apagada. La residencia de bajo consumo de cada subsistema/SoC no se deduce únicamente de la suspensión del sistema. No hay comparación controlada con rc4/R10 o con el módulo CPU habilitado.

El contador de carga baja 64000 µAh, equivalente aproximadamente a 177 mA de promedio durante el intervalo si ese sensor mantiene su escala. Es una estimación del sensor que incluye las capturas y otras actividades; las lecturas instantáneas de corriente con pantalla encendida no representan el consumo dormido.

## Eventos concretos y límites

- El driver Wi-Fi `icnss2` rechazó nueve suspensiones en `suspend_noirq` con `-11`. El último dispositivo fallido es `c800000.qcom,icnss`. Se registraron además 54 motivos de despertar `WLAN_CE_2`. Son indicios concretos para aislar la participación de Wi-Fi; no demuestran una regresión causada por los parches rc5.
- Hay 103 eventos de aborto con `[timerfd]` pendiente y cuatro motivos de tareas que rechazaron congelarse. El contador global registra cinco fallos de freeze. El informe no identifica los propietarios históricos de esos temporizadores ni las tareas. Las categorías de motivos y fallos no se suman como si fueran intentos independientes.
- `PowerManagerService.WakeLocks` aumenta 484,853 s, unos ocho minutos. Es el agregado de bloqueos parciales del framework; no identifica una app responsable de todo el intervalo. Al final aparece un trabajo de WhatsApp adquirido unos 22 s antes. Eso no permite atribuirle los ocho minutos anteriores ni justifica restringir sus notificaciones.
- Se registran 14 backoffs nuevos y cinco continuaciones. Hay 25,017 s de overhead de suspensión y 4,037 s de overhead fallido; no se deben presentar como duración total de cada motivo de despertar.
- `MediaProjection=null` y la pantalla remota desconectada en ambos extremos. No hubo proyección activa en esos instantes; esto no cubre todo el intervalo ni todos los protocolos de reproducción remota.
- `Awake`, bloqueo de pantalla y autosuspend HAL desactivado en los extremos coinciden con el usuario operando el recolector. No invalidan los contadores del tramo con pantalla apagada. Los tiempos de `dmesg` emplean otro reloj y los pares de mensajes PM separados por unas décimas no miden por sí solos cuánto durmió realmente el teléfono.
- `-1 misconfigured IRQ 22 mpm` aparece tres veces. Ese número no debe confundirse automáticamente con una IRQ global ni deshabilitarse sin identificar el dominio y el driver. El informe no demuestra el origen de esa configuración.

## CPU, memoria y perfiles

El módulo CPU tiene marcador de desactivación y los registros disponibles muestran tasas WALT de 0 µs sin ajuste aplicado. El módulo de memoria aparece pausado; el watermark runtime es 1 y MGLRU está activo. No hay base para atribuir a un ajuste CPU nuestro el resultado observado. Los flags de GPU force_clk_on/force_bus_on/force_rail_on son 0 en ambos extremos.

La zRAM actual es de 2 GiB lógicos en ambos extremos: empieza casi llena y termina con aproximadamente 346 MiB libres. Su consumo físico pasa de 702 a 574,5 MiB. MemAvailable pasa de 601,4 a 1053,1 MiB. Los snapshots antiguos incluidos en el historial del módulo, que muestran 3 GiB y otros contadores, pertenecen a otra observación y no se restan contra esta prueba.

Los deltas PSI respecto del intervalo de 1303,09 s son memoria some 1,17% / full 0,86%, CPU some 2,72%, I/O some 1,45% / full 0,74%. Son fracciones de tiempo de presión, no uso de CPU. Kswapd acumula unos 24 s adicionales de CPU. El contador oom_kill permanece en 0; no descarta terminaciones de LMKD. Estos datos no son una prueba de uso activo de TikTok ni se comparan directamente con sus capturas históricas de carga.

## Siguiente comprobación acotada

Repetir una sola captura de reposo con el mismo módulo durante unos diez minutos, **Wi-Fi apagado y datos móviles activos si están disponibles**, conservando WhatsApp, módulos necesarios y los demás ajustes. Mantener CPU Respuesta desactivado. Así se puede observar si desaparecen los rechazos ICNSS y cuánto cambia la fracción de suspensión y los bloqueos del framework. Cambiar de red también cambia la carga de comunicaciones; no será una prueba aislada perfecta de una línea del driver.

Si no hay datos móviles disponibles, conservar WhatsApp conectado y acordar otra comparación: no se solicita modo avión ni desconexión permanente. Falta identificar propietarios históricos de wakelocks/temporizadores para corregir una causa concreta; no se justifica publicar un kernel nuevo atribuyéndole una solución aún no comprobada.
