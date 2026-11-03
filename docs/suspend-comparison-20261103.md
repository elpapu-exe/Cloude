# Comparación de los dos informes de reposo de rc5

Se comparan exclusivamente los contadores START/END de cada informe, excluyendo snapshots antiguos dentro del historial del módulo. Ambos terminan con TEST FINISHED. No se publica el TXT original ni identificadores personales.

| Medida | Primer informe | Segundo informe |
| --- | --- | --- |
| Intervalo | 1303,09 s (21 min 43 s) | 985,88 s (16 min 26 s) |
| Suspensión por relojes | 757,35 s (58,1%) | 433,48 s (44,0%) |
| Fracción aproximada del tiempo de pantalla apagada suspendida | 59,4% | 45,4% |
| Pantalla apagada | 1274,255 s | 955,551 s |
| Pantalla encendida, batterystats | 28,787 s | 32,778 s |
| Temperatura de batería | 40 → 37 °C | 38 → 38 °C |
| Indicador de batería | 34 → 33% | 31 → 28% |
| Incremento de éxitos / fallos de suspensión | 160 / 19 | 43 / 50 |
| Incremento de fallos ICNSS / motivos WLAN_CE_2 | 9 / 54 | 0 / 0 |
| Incremento de motivos timerfd pendiente | 103 | 39 |
| Bloqueo parcial agregado del framework adicional | 484,853 s | 271,377 s |
| watermark runtime | 1 en ambos extremos | 64 en ambos extremos |

Los relojes del segundo informe coinciden con el incremento de SuspendInfo de 433477 ms. Su contador total de 1949168 ms y sus 122 fallos al final pertenecen a todo el arranque; no deben presentarse como los de esta prueba.

## Qué cambia la interpretación

En el segundo tramo ICNSS permanece en 42 y WLAN_CE_2 en 163. No aumentaron esos eventos de Wi-Fi. Esto es consistente con la comparación solicitada, pero el recolector rc1 no registra el transporte de red y el usuario todavía debe confirmar qué conexión utilizó.

También cambió la configuración de memoria: watermark pasó de 1 a 64 entre informes y el marcador de pausa del módulo de memoria desapareció. Esto es compatible con su reactivación u otro cambio de parámetros, sin identificar por sí solo quién escribió el valor. La zRAM actual conserva 2 GiB. No es una comparación que cambie únicamente la red, ni permite atribuir a un parámetro el descenso de suspensión.

## Eventos nuevos y origen aún sin resolver

Los fallos del segundo tramo pasan de 72 a 122: 40 adicionales en la fase freeze y 10 en suspend. Los motivos `Last active Wakeup Source: qrtr_ws` pasan de 14 a 62, y hay mensajes contemporáneos de ese tipo dentro del intervalo medido. QRTR comunica servicios Qualcomm con otros subsistemas; el nombre no identifica una aplicación ni exclusivamente el módem.

Hay dos límites esenciales del código revisado:

- `failed_freeze` incluye abortos por eventos de despertar, además de timeouts. Los motivos explícitos `One or more tasks refusing to freeze` permanecen en 4. No se puede traducir ese incremento en cuarenta tareas que rechazaron congelarse.
- Cuando no hay una fuente activa, el kernel puede mostrar la última conocida. Los 48 motivos con etiqueta QRTR no demuestran 48 paquetes diferentes ni causalidad individual de cada fallo. Son una pista para investigar el tráfico y los clientes, no una autorización para bloquear QRTR.

Las continuaciones de backoff aumentan de 25 a 66 y el contador de tiempo entre intentos aumenta 342,9 s. Se solapan con otras actividades y no deben sumarse al tiempo de wakelocks como duraciones independientes.

El nombre ICNSS persiste en last_failed_dev, junto a un paso posterior freeze y error -16. Los campos conservan información de fallos anteriores; no acreditan un fallo nuevo del callback Wi-Fi. La GPU conserva sus tres force_* en 0 y CPU Respuesta sigue desactivado. La proyección de pantalla es null en ambos extremos.

Un trabajo de WhatsApp está visible al inicio y no al final de la lectura power. No hay historial de propietarios suficiente para responsabilizarlo del bloqueo agregado. Las consultas son secuenciales: una tabla posterior puede mostrar un estado más reciente.

## Decisión y diagnóstico actualizado

No se cambia el kernel, el freezer, QRTR, límites CPU/GPU ni reglas de red. El Image no incluye QRTR, pero la receta vendor sí solicita qrtr.ko; modificar solamente una implementación no incorporada en Image no acredita cambiar el módulo cargado.

El recolector rc2 conserva las dos pulsaciones y ningún proceso entre ellas. Añade procesos de usuario antes del límite de salida, módulos relevantes sin direcciones, flags de configuración de red y contadores de interfaces sin IP/SSID, totales de wakelocks por UID, correspondencia con paquetes y sumas de alarmas sin sus tags. Conserva por separado los mensajes del freezer para que los mensajes PM repetidos no los desplacen.

Se emplea `dumpsys batterystats --charged`. En el código de Android 13, `--checkin` puede consumir un archivo de un ciclo anterior, y `-c` incluye historia; no se utilizan. Los valores por UID pueden solaparse o representar varios paquetes que comparten UID: no se suman como tiempo transcurrido ni identifican todos los posibles timerfd nativos.

Para una siguiente captura, volver a una configuración estable y conservarla durante todo el intervalo: CPU Respuesta y Fluidez Memoria desactivados durante este diagnóstico, reinicio para retirar sus efectos, conexión habitual que mantenga WhatsApp, resto de módulos necesarios y térmicas conservados. No se exige otra alternancia de redes. El objetivo es identificar actividad y propietarios, no forzar una mejora del porcentaje.

La actualización rc2 quedó [publicada con descarga verificada](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-reposo-diagnostico-0.1.0-rc2-9d6ab6d12c08-41702509577). Pasaron 21 pruebas sin omisiones, también desde su ZIP de fuentes aislado; cinco assets descargados y cuatro hashes comprobados dos veces. [Evidencia propia](reposo-module-release-rc2.json). No se compiló otro kernel.
