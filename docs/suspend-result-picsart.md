# Tercer informe: aplicación candidata y actividad de arranque

El informe de Reposo Diagnóstico v2 termina con TEST FINISHED. Comienza aproximadamente 62 s después de reiniciar y dura 620,58 s. La identidad observada sigue siendo rc5. Los módulos CPU Respuesta y Fluidez Memoria tienen marcadores de desactivación; watermark vale 1 en ambos extremos. No se publica el TXT original ni el inventario de aplicaciones/UID.

## Resultado

- Suspensión por relojes: 11,29 s, 1,8% del intervalo. SuspendInfo registra 11251 ms, consistente con el muestreo secuencial.
- Batería: 40 → 41 °C; indicador 22 → 18%.
- Pantalla apagada, delta de batterystats: 584,753 s; pantalla encendida: 25,841 s. Estos contadores se leen después de los relojes, por lo que su intervalo no es exactamente el mismo.
- 46 intentos de suspensión, nueve marcados exitosos y 37 fallos. De estos, 33 corresponden a la fase freeze; no aparecen timeouts de tareas identificadas en los mensajes retenidos.
- Hay 32 motivos con la etiqueta de última fuente QRTR y los mensajes dicen `Freezing of tasks aborted` tras 2–20 ms. Como en las capturas anteriores, última fuente no significa atribución causal exclusiva.
- Configuración registrada: Wi-Fi 0, datos móviles 1, modo avión 0; QRTR aparece cargado como módulo vendor. No hay fallos ICNSS nuevos en este arranque.

Esta captura reproduce muy poca suspensión y aumento de temperatura, pero incluye actividad del primer minuto tras arrancar. No es una comparación controlada con un sistema ya estabilizado.

## Picsart: primer candidato concreto de aplicación

El periodo de batterystats coincide en ambos extremos. Picsart tiene correspondencia de paquete al inicio sin fila TOTAL wake; al final aparece con 7 min 0,656 s de `actual partial`, también en background, y 5 min 35,614 s de `blamed partial`. No hay aviso de truncamiento de ese lector. El usuario confirmó que no estaba editando, exportando ni subiendo un proyecto en Picsart durante la captura.

Es la mayor atribución nueva de aplicación observada y justifica aislarla primero. No demuestra una fuga, un defecto concreto de Picsart ni que causara todos los problemas históricos o la actividad QRTR.

**Límite de contabilidad:** el valor atribuido a Picsart supera los 264,989 s de aumento del bloqueo nativo PowerManagerService.WakeLocks. No se asume que ambos contadores sean intercambiables ni que la diferencia esté resuelta. Por tanto, no se presenta como siete minutos medidos en los que Picsart impidió físicamente suspender, ni como un porcentaje causal del intervalo.

Otros incrementos de `actual partial` son WhatsApp 75,405 s, Instagram 33,843 s, servicios de Google 30,122 s y Messenger 18,834 s. Sus horas acumuladas anteriores no pertenecen a este ensayo. Los tiempos de UID pueden solaparse; no se suman como tiempo transcurrido. WhatsApp conserva su prioridad de notificaciones.

## Cambio específico y reversible

Conservar el kernel, módulos personales necesarios y protecciones térmicas. Mantener nuestros dos perfiles experimentales desactivados durante esta comparación. Después de guardar cualquier proyecto abierto:

1. Ajustes → Aplicaciones → Picsart → **Forzar detención**.
2. En el apartado de batería de esa aplicación, seleccionar **Restringido** si la ROM ofrece la opción. Restringe solo Picsart. Las tareas o subidas de Picsart en segundo plano pueden retrasarse; sus proyectos no se borran y puede abrirse manualmente.
3. Observar el reposo con la conexión habitual y sin cambios adicionales. Para comprobarlo con registros, usar el mismo diagnóstico v2 durante unos diez minutos cuando hayan transcurrido al menos cinco minutos desde el arranque; no hace falta reiniciar para ese cambio de aplicación.

Todavía no se verificó el resultado de esa intervención en el teléfono. No se compila otro kernel, no se fuerza suspensión y no se bloquean QRTR, servicios de telefonía, Google o WhatsApp.
