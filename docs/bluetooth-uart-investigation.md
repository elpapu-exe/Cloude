# Bluetooth encendido sin conexiones: siguiente fase de diagnóstico

El usuario confirmó dos datos: el único cambio antes de recuperar 92,5% de suspensión fue apagar Bluetooth, y anteriormente estaba encendido **sin dispositivos conectados**. Esto refuerza considerablemente la asociación entre Bluetooth, la retención de UART y la falta de reposo en este teléfono. No se atribuye a consumo normal de una sesión de audio ni se declara identificado el defecto interno del driver/HAL.

La fuente UART dejó de sumar actividad; el periodo de batería se conservó y los contadores independientes concordaron. [Resultado medido](suspend-result-uart-released.md). No se modificó el kernel entre las dos situaciones.

## Por qué falta identificar el componente antes de corregirlo

La configuración del Image tiene SERIAL_MSM_GENI desactivado; la receta vendor lo solicita como módulo. Cambiar solo su fuente local y recompilar Image no sustituye el módulo instalado por la ROM. Tampoco basta que los CRC públicos coincidan para demostrar el origen de ese módulo.

El controlador local conserva un wakelock mientras UART está activa y lo libera al suspenderla. La revisión no encontró una fuga demostrada en el camino normal. Hay mecanismos que requieren distinguir con información del teléfono:

- Un cliente puede conservar un voto. PMPUT devuelve -EAGAIN sin quitarlo cuando RX no termina; importa si el cliente reintenta.
- La suspensión runtime puede fallar al apagar recursos y conservar la fuente activa; el estado runtime puede mostrar error.
- Runtime PM puede estar impedido por configuración o por un modo DT particular. No se fuerza power/control ni se oculta el wakelock para cambiar un porcentaje.

Abrir la propia UART para probarla cambia su ciclo de vida, por lo que el diagnóstico no lo hace. No se bloquea el servicio Bluetooth ni se impone apagarlo permanentemente.

## Ampliación rc3 del recolector existente

Se añaden únicamente lecturas:

- Flags Bluetooth y BLE scan, más una lista fija de propiedades de sleep/configuración y del vendor. No se vuelcan todas las propiedades ni nombres/direcciones de dispositivos Bluetooth.
- Estado del adaptador y filas numéricas de escáneres BLE en el formato Lineage 20 verificado: paquetes, contadores y tiempo. El dump bruto no se guarda; se excluyen nombres/direcciones de accesorios, filtros y UUID. Las filas históricas o una sección de escaneo no demuestran qué retiene UART. Un formato desconocido se declara no disponible.
- Alias DT hsuart y enlaces ttyHS/device, of_node y driver para mapear el puerto real.
- Estado, control y tiempos runtime PM, atributos de wakeup que estén expuestos y presencia del booleano DT auto-suspend-disable, incluso si su archivo tiene cero bytes.
- Enlace al módulo cargado, versión/srcversion y SHA256 de candidatos de archivo en ubicaciones fijas. Un hash identifica bytes; no demuestra fuente exacta.
- Descriptores apuntando a ttyHS en procesos Bluetooth candidatos, leyendo solo enlaces. No se abren dispositivos ni se leen buffers, argumentos, otros archivos de FD o paquetes Bluetooth. Un resultado ausente no demuestra puerto cerrado; la búsqueda es acotada y puede estar limitada por permisos.

Los valores ausentes no se sustituyen por un valor predeterminado. Las propiedades SIBS son pistas de configuración de implementaciones Qualcomm conocidas; su existencia o ausencia no demuestra que el HAL de esta ROM las utilice. Pasan 31 pruebas, incluidas lecturas ausentes, privacidad, encabezados vendor desconocidos, estado PM y descriptores UART. Las pruebas simulan Android y no sustituyen la primera lectura real.

## Captura breve, mismo módulo

Actualizar Reposo Diagnóstico a rc3 y reiniciar si el Manager lo requiere. Mantener los perfiles experimentales CPU Respuesta/Fluidez Memoria desactivados, Wi-Fi/datos para WhatsApp y los módulos personales necesarios.

1. Con cargador/USB desconectados, encender Bluetooth **sin conectar accesorios** y esperar aproximadamente un minuto.
2. Pulsar Acción y esperar START SAVED.
3. Apagar Bluetooth, esperar unos diez segundos y pulsar Acción de nuevo hasta TEST FINISHED.
4. Compartir el mismo tipo de TXT de Descargas.

Esta captura compara estados antes/después de apagar Bluetooth. **Su porcentaje de reposo no evalúa la mejora de deep sleep**: es intencionadamente breve y se opera con la pantalla encendida. No requiere repetir diez minutos de pantalla apagada en esta fase, otro kernel ni modificar frecuencias.

## Referencias

- [Votos y runtime PM GENI serial](../kernel-source/linux/drivers/tty/serial/msm_geni_serial.c).
- [IOCTL usados por clientes BT](../kernel-source/linux/include/uapi/linux/msm_geni_serial.h).
- [Configuración efectiva del Image](../config/effective.config).
- [Receta vendor topaz](../kernel-source/linux/arch/arm64/configs/vendor/topaz_GKI.config).
- [Ejemplo Qualcomm antiguo que consulta persist.vendor.service.bdroid.sibs](https://github.com/Micronet-Ltd/android9_vendor/blob/df881a2346443784c1e3574125b7d7d31d567485/qcom/proprietary/bt/hci_qcomm_init/wcnss_filter/src/hw_cherokee.c). No es identificación de la implementación instalada.
- [Formato del estado Bluetooth en Lineage 20](https://github.com/LineageOS/android_packages_modules_Bluetooth/blob/lineage-20.0/service/java/com/android/server/bluetooth/BluetoothManagerService.java).
- [Mapa de escáneres GATT](https://github.com/LineageOS/android_packages_modules_Bluetooth/blob/lineage-20.0/android/app/src/com/android/bluetooth/gatt/GattService.java) y [filas de estadísticas BLE](https://github.com/LineageOS/android_packages_modules_Bluetooth/blob/lineage-20.0/android/app/src/com/android/bluetooth/gatt/AppScanStats.java). Referencias de formato, no identificación del HAL instalado.
