# Estado y continuación

**Confirmación del usuario:** apagar Bluetooth fue el único cambio de la prueba con 92,5% de reposo; antes estaba encendido sin dispositivos conectados. Rc3 del diagnóstico existente está [publicado](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-reposo-diagnostico-0.1.0-rc3-8c6010416a2e-41903620910) tras 31 pruebas, cinco assets descargados y verificados y auditoría independiente del ZIP de fuentes. Lee enlace TTY/UART, runtime PM, módulo vendor, propiedades fijas, escáneres BLE y descriptores de clientes. [Evidencia](docs/reposo-module-release-rc3.json). No se fuerza un clock-off ni se modifica Image: falta identificar el componente real. [Fase actual](docs/bluetooth-uart-investigation.md).

**Quinto informe: reposo recuperado en esta prueba.** 898,70 s suspendido de 971,25 s (92,5%), temperatura 40 → 38 °C. UART y USB inactivos sin nueva actividad; QRTR no añade abortos y se reanudan los intentos de suspensión. El periodo de aplicaciones no se reinició. El usuario confirmó posteriormente que solo apagó Bluetooth, antes activo sin accesorios. La asociación es fuerte; el defecto interno aún no está identificado y no se declara una reparación permanente. [Resultado](docs/suspend-result-uart-released.md). No se cambió ni compiló otro kernel/módulo para este análisis.

**Cuarto informe analizado:** casi doce horas, batería 18 → 100% y reinicio de batterystats. UART `4a8c000.qcom,qup_uart` permanece Active y añade 42735,633 s de actividad; USB añade 42703,192 s durante la carga. No aumentan intentos/fallos de suspensión. El total HAL de sueño es inválido. Se investiga el cliente UART, con Bluetooth como hipótesis pendiente de confirmación; no se atribuye la noche a datos UID de otro periodo. [Resultado](docs/suspend-result-uart.md). No se cambió ni compiló otro kernel o módulo.

**Tercer informe rc2 analizado:** 11,29 s suspendido en 620,58 s, batería 40 → 41 °C; comienza a los 62 s del arranque. Perfiles CPU/memoria desactivados, watermark 1. Batterystats atribuye a Picsart 7 min de actual partial/background, la mayor atribución nueva; el usuario no lo utilizaba. Hay límites de contabilidad frente al agregado nativo y abortos QRTR concurrentes. El siguiente cambio es restringir únicamente Picsart y comprobar con el recolector existente, conservando WhatsApp y módulos necesarios. [Resultado](docs/suspend-result-picsart.md). No se cambió el kernel ni se añadió otro módulo.

**Segundo informe analizado:** 433,48 s de suspensión en 985,88 s; batería 38 → 38 °C. No aumentaron ICNSS/WLAN, pero sí fallos de freeze y abortos etiquetados con la última fuente QRTR. Watermark cambió a 64 y memoria ya no figura pausado, impidiendo atribuir todo a la red. Se publicó diagnóstico rc2 de atribución con 21 pruebas y descarga verificada, sin ajustes ni nuevo kernel. [Comparación](docs/suspend-comparison-20261103.md).

**Primer informe de reposo analizado:** suspensión real de 757,35 s en 1303,09 s, consistente con SuspendInfo; batería 40 → 37 °C. Registra nueve fallos ICNSS, despertares Wi-Fi, temporizadores pendientes y unos ocho minutos agregados de bloqueo parcial Android sin propietario histórico identificado. CPU Respuesta está desactivado, memoria pausado. [Resultado y siguiente comparación](docs/suspend-result-20261103.md). No se modificó ni solicitó otro kernel para este análisis.

**Observación posterior: reposo/temperatura.** Una captura identifica rc5 arrancada, batería a 44 °C y 8 min 57 s de suspensión indicada entre 13 h 26 min 57 s de uptime. No conocemos el tiempo de pantalla apagada ni la causa. Se publicó un diagnóstico independiente de dos pulsaciones sin proceso entre ellas, con 16 pruebas y descarga verificada; no se solicitó otro kernel. [Investigación y pasos](docs/suspend-investigation.md). La validación de compilación siguiente conserva su alcance histórico.

**0.1.0-rc5 compilada, auditada y publicada** por [Actions 41290063824](https://github.com/elpapu-exe/Cloude/actions/runs/41290063824), desde `9c81476ba0a6ffc452d5fdb5463cf5cebf128ad9`. [Entrega](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc5-9c81476ba0a6-41290063824) · [Evidencia completa](docs/ci-build-result-rc5.json).

ZIP: 25,216,619 bytes; SHA256 `0d419065b704c276e12055a0ddb0d1a4126893d898b2fa0032f07b161dfaa4cc`. Fuentes tar.zst: 195,383,642 bytes; SHA256 `3559b47d1fea259ce63cd408ff3b1981a79d2d4957521ad485f8d68eb864403a`. Se conservan como assets, fuera del historial Git normal.

## Validación de rc5

- ARM64 completo, Full LTO/O2, CFI, SCS, BTF, MODVERSIONS y protecciones térmicas conservados.
- 93 pruebas obligatorias, sin fallos ni omisiones, sobre el árbol compilado; replay previo de 18 parches sobre 40 archivos finales.
- 15.543 exports y CRC idénticos a R10; ningún símbolo añadido, ausente o cambiado. Esto no prueba los módulos concretos del teléfono.
- IKCONFIG idéntica a la configuración efectiva e inicializador ELF watermark=10.
- Archivo final de fuentes: 77.010 entradas verificadas por contenido, tipo, modo y destinos literales de enlaces.
- 35 assets descargados y verificados antes de publicar: 34 hashes comprobados dos veces, más comparación del propio SHA256SUMS.

Runner observado: dos CPU, aproximadamente 7,75 GiB RAM, 28 GiB de swap adicional. Full LTO/Image: 52 min 15 s con paginación considerable. El éxito corresponde a esta configuración medida. Avisos BTF: filp_close, should_failslab, vfs_getattr.

La configuración difiere de rc4 solo en LOCALVERSION. Los cambios nuevos protegen caché reutilizada en MGLRU y retiran el filtro CMA problemático en reclaim. [Revisión](docs/community-review-rc5.md). No se modifican zRAM, LMKD, swappiness, frecuencias o voltajes.

## Módulo CPU publicado

ChatGPT CPU Respuesta 0.1.0-rc1: [entrega](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-cpu-respuesta-0.1.0-rc1-7b0a51d49a6b-41291184310) · [evidencia](docs/cpu-respuesta-release.json). ZIP 24,960 bytes; SHA256 `0a0070959d330c901860a876305640c9c099a53e6fda2d9135fb007fe4e07a90`. Sus 33 pruebas y cinco assets fueron verificados en una ejecución independiente. Solo ajusta condicionalmente WALT up_rate_limit_us; Acción recoge 180 segundos con el recolector v7. El kernel rc5 congelado contiene v6 y 93 pruebas. No se modificó el módulo de memoria.

## Observaciones y siguiente prueba

Los informes identifican rc4, MGLRU activo y WALT seleccionado desde vendor. El primero dura unos 15 segundos al arrancar. El segundo contiene unas 4 h 22 min del mismo arranque con presión de memoria/IO, cambios de zRAM de 2 a 3 GiB y límites CPU diferentes. No permite atribuir una mejora o regresión a un parámetro concreto. El usuario identifica SmartPack como gestor de zRAM; [persistencia](docs/smartpack.md). Los informes originales y sus identificadores no se publicaron.

**Pendiente en el teléfono:** comprobación de funciones básicas de rc5, root/módulos, WhatsApp, estabilidad, fluidez y temperatura. La captura posterior identifica rc5 arrancada. Una captura de tres minutos con Acción del módulo CPU mantiene el perfil actual, WhatsApp y los módulos necesarios. El módulo es opcional; para comparar kernels mantén los mismos ajustes. [Procedimiento](docs/testing.md).

## Historia conservada

[rc4](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc4-0640e8f41412-40663572783) y [rc3-rebuild1](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-kernel-0.1.0-rc3-rebuild1-a01d67ebe63f-40633724058) conservan resultados propios. El [módulo de memoria](docs/fluidez-module-release.json) mantiene su versión y estado independiente.

Este checkout comenzó desde el remoto 4fc1ad554ac54ffce0a6792ca6d85f67435e8a86, rama chatgpt-kernel-download; main no existía. El commit rc2 local y rc3 sin publicar no se recuperaron. El entorno anterior no se borró ni sobrescribió. rc3-rebuild1 fue una reconstrucción nueva. KSU utiliza su historia original completa para conservar 35142; no se fabricó un historial Git.

Los documentos dentro de los assets son el snapshot del commit compilado. La actualización posterior de documentación conserva los binarios auditados y no solicita otra compilación.

## Diagnóstico inicial rc1 de reposo publicado

[Entrega](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-reposo-diagnostico-0.1.0-rc1-4f9bb7003ac2-41673413289), commit `4f9bb7003ac29435fd314b74d41b3530a1e90518`, [Actions41673413289](https://github.com/elpapu-exe/Cloude/actions/runs/41673413289). Build y publish terminaron SUCCESS; 16 pruebas sin omisiones, fuente ZIP comprobada también de forma independiente, cinco assets descargados y cuatro hashes comprobados dos veces. ZIP 14613 bytes, SHA256 `a1bad7a9f41afc230dd130fe37c2521925dcc7cdc2025f4ae81eecde1472007f`. [Resultado](docs/reposo-module-release.json). No tiene servicio ni tareas de arranque, temporizadores o wakelocks. Su primer informe real ya fue analizado; los relojes coinciden con SuspendInfo y la causa de los despertares sigue en investigación.

## Diagnóstico rc2 publicado

[Entrega](https://github.com/elpapu-exe/Cloude/releases/tag/chatgpt-reposo-diagnostico-0.1.0-rc2-9d6ab6d12c08-41702509577), commit `9d6ab6d12c08dcf1c74e170e394a58af4c0317d7`, [Actions41702509577](https://github.com/elpapu-exe/Cloude/actions/runs/41702509577). Build/publish SUCCESS, 21 pruebas sin omisiones; source ZIP ejecutado de forma independiente; cinco assets descargados y cuatro hashes comprobados dos veces. ZIP 16399 bytes, SHA256 `cc18cb085e979c6a4b3613d5eb006b3a20db54d56a6ed9d51ddfad3716fc2e35`. [Resultado](docs/reposo-module-release-rc2.json). Incluye atribución UID, totales de alarmas sin tags y mensajes del freezer separados; mantiene cero procesos entre capturas y no cambia parámetros del teléfono. No hubo nueva compilación del kernel.
