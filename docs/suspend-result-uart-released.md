# Quinto informe: reposo recuperado con la fuente UART inactiva

El informe rc2 termina con TEST FINISHED y conserva el mismo arranque y periodo de batterystats durante el intervalo. No incluye una carga ni un reinicio contable. Se publica solo este resumen; no el TXT ni el inventario de aplicaciones/UID.

| Medida | Resultado |
| --- | --- |
| Intervalo por reloj BOOTTIME | 971,25 s: 16 min 11 s |
| Suspensión por diferencia BOOTTIME/MONOTONIC | 898,70 s: 14 min 59 s, 92,5% |
| Incremento del tiempo de suspensión HAL | 898698 ms, consistente con los relojes |
| Pantalla apagada, delta de batterystats | 955,917 s |
| Fracción aproximada del tramo apagado suspendida | 94,0% |
| Temperatura de batería | 40 → 38 °C |
| Indicador de batería | 43 → 42% |
| Nuevos intentos / éxitos / fallos de suspensión | 117 / 104 / 13 |

Se recuperó una suspensión mayoritaria en esta configuración. Esto mide reposo del sistema durante este intervalo, no residencia mínima de todos los subsistemas, autonomía prolongada ni mejora de fluidez de TikTok. El valor absoluto del tiempo HAL sigue siendo inválido; únicamente su incremento se contrastó con los relojes independientes.

## Cambio de la fuente retenida

`4a8c000.qcom,qup_uart` está Inactive en ambos extremos, con active count 16, tiempo total 72561731 ms y última transición 79945525 ms idénticos. No añade actividad durante la prueba. La última transición se produjo aproximadamente 34 s antes del reloj START.

El USB permanece inactivo y no añade actividad. Comparado con el END del informe anterior, sus contadores siguen idénticos: la UART había continuado retenida durante casi las cinco horas y veintidós minutos posteriores a desconectar la carga, hasta poco antes de esta captura. Por tanto, el bloqueo UART no queda explicado solo por la carga nocturna.

Los motivos con la etiqueta de última fuente QRTR permanecen en 33. La lectura wakeup_count vuelve a entregar números y se reanudan los intentos de suspensión. Esto refuerza la relación entre liberar la fuente UART y recuperar el reposo.

El informe no registra por sí solo el estado Bluetooth. Posteriormente el usuario confirmó que apagarlo fue el único cambio y que estaba encendido sin accesorios conectados. Esto refuerza la asociación Bluetooth/UART/reposo en este teléfono; todavía falta identificar el defecto interno o cliente que retiene el puerto. [Siguiente fase y captura breve](bluetooth-uart-investigation.md). No se exige que permanezca apagado permanentemente.

## Aplicaciones y eventos residuales

Los periodos de batterystats coinciden. WhatsApp añade 7,722 s de actual partial, el UID del sistema 5,288 s y Google búsqueda 1,554 s; Instagram y Messenger no incrementan sus tiempos. Picsart no aparece en ninguna lista, sin nueva atribución observable en este periodo. No se suman contadores de UID como tiempo transcurrido ni se interpretan las horas acumuladas como actividad de este ensayo.

El bloqueo parcial nativo del framework añade 19,041 s y Display 16,592 s. Los módulos CPU Respuesta y Fluidez Memoria siguen desactivados; watermark vale 1 y la zRAM conserva 2 GiB lógicos.

Persisten 13 fallos nuevos: ocho en freeze, dos en suspend y tres en ICNSS/noirq. WLAN añade 28 motivos de despertar y timerfd 71 de pendiente. No impidieron lograr el reposo mayoritario. No se promete un objetivo universal de 99% ni se justifica desactivar notificaciones o red por esos contadores.

El contador de carga baja 24000 µAh, aproximadamente 89 mA medios si mantiene su escala. Incluye las capturas y no constituye por sí solo una medición de consumo estable dormido ni de autonomía.

## Continuación

Conservar provisionalmente la configuración que produjo este resultado, WhatsApp y los módulos personales necesarios. La confirmación del usuario ya llegó; el siguiente dato necesario es la identidad y estado runtime del módulo UART y su cliente. Se prepara una ampliación pasiva del recolector existente para esa lectura, sin recompilar Image ni aplicar un parche de Bluetooth/UART.
