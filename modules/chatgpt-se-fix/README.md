# ChatGPT SE Fix 0.1.0-rc1

Módulo **experimental** de LSPosed para el Redmi Note 12 4G `tapas` con la ROM Android 13 investigada. Su objetivo es cortar el bucle de ANR de SecureElement al esperar un HAL `eSE1` que no aparece registrado. Necesita una primera prueba en el teléfono; no garantiza solucionar los bloqueos de TikTok.

## Qué hace

Intercepta `com.android.se.Terminal.initialize(boolean)` únicamente dentro del paquete y proceso `com.android.se`. Cambia el argumento de espera de `true` a `false` cuando se cumplen **todas** estas condiciones:

- Android 13, SDK 33, y `Build.DEVICE` igual a `tapas`.
- El terminal se llama exactamente `eSE1` y la llamada original solicita esperar.
- El sistema declara `android.hardware.se.omapi.uicc` y no declara `android.hardware.se.omapi.ese`.

La consulta al HAL se ejecuta igualmente. Si el eSE está registrado, la inicialización original puede utilizarlo; si falta, Android puede continuar con la inicialización de los terminales SIM. Los argumentos de `SIM1`, `SIM2` y los demás terminales se conservan. Un error al comprobar las condiciones deja el argumento original.

El APK no solicita permisos, no accede a la red y no tiene actividad de inicio. LSPosed carga el código en el proceso seleccionado. La instalación no modifica particiones, firmas del sistema, reglas SELinux ni ajustes de CPU o memoria.

## Instalación y comprobación

1. Descarga e instala [ChatGPT-SE-Fix-0.1.0-rc1.apk](../../downloads/ChatGPT-SE-Fix-0.1.0-rc1.apk) como una aplicación normal.
2. Abre LSPosed, entra en **Módulos** y activa **ChatGPT SE Fix**. Selecciona únicamente **SecureElement**, paquete `com.android.se`, como ámbito. Si la lista oculta aplicaciones del sistema, habilita su visualización.
3. El hook se carga en el siguiente inicio del proceso SecureElement. Si sigue el bucle de ANR observado, ese proceso se recrea aproximadamente cada veinte segundos; espera a que se produzca esa recreación. Habilitar el módulo no modifica una instancia que ya esté ejecutándose.
4. Ejecuta el [recolector breve](../../downloads/chatgpt-secureelement-logs.sh) y comparte su archivo de texto:

```sh
su -c '/system/bin/sh /sdcard/Download/chatgpt-secureelement-logs.sh'
```

La comprobación debe buscar la aparición del servicio Binder SecureElement y que dejen de producirse ANR nuevos de ese proceso. Los eventos antiguos permanecen en el registro y, por sí solos, no prueban que el módulo haya fallado. Hay que comprobar también el funcionamiento de las funciones SIM utilizadas; la presencia del servicio Binder no valida todas ellas.

En el registro de LSPosed, el prefijo `ChatGPT SE Fix:` indica si se instaló el hook y si se aplicó la consulta sin espera a `eSE1`. El módulo no recoge ni sube registros automáticamente.

## Límites y reversión

Si el dispositivo tiene un eSE legítimo que se registra tarde y la ROM omite su feature, este parche podría dejar de descubrirlo durante esa instancia del proceso. Está limitado al caso investigado y no debe distribuirse como un ajuste general de rendimiento. Tampoco corrige la presión de memoria, las restricciones por temperatura ni todos los posibles fallos de TikTok.

Para retirarlo, desactívalo en LSPosed y desinstala el APK. El hook deja de estar activo cuando se reinicia el proceso SecureElement; reiniciar el teléfono también garantiza esa recreación. No deja un servicio propio ni un cambio persistente de configuración.

## Compilación y alcance de las pruebas

Desde la raíz del repositorio:

```sh
bash scripts/build-se-fix.sh
```

El constructor utiliza las herramientas y verificaciones descritas en ese script y genera el APK y su manifiesto de compilación en `dist/`. Los descriptores de API Xposed de `compile-only/` solo sirven de classpath y deben quedar excluidos de las clases definidas del APK.

Las pruebas de código y empaquetado no sustituyen la comprobación en el teléfono. El código se basa en la ruta de inicialización de [AOSP SecureElement en Android 13](https://github.com/aosp-mirror-neo/platform_packages_apps_SecureElement/tree/android-13.0.0_r75/src/com/android/se): `createTerminals()` intenta eSE antes de SIM, y `Terminal.initialize()` transmite el argumento de espera a las consultas HIDL 1.2, 1.1 y 1.0.
