# Compatibilidad de ChatGPTKernel con la instalación actual

Esta revisión cubre la base funcional Zepharo R10 y las condiciones que debe mantener la compilación. No certifica todavía una imagen nueva: faltan sus artefactos finales y no se ha probado en el teléfono.

## Referencia y alcance

- Dispositivo informado: Redmi Note 12 4G, `topaz`/`tapas`, 4 GB de RAM.
- Sistema que se conserva: `lineage-20.0-20231209-UNOFFICIAL-topaz`, Android 13.
- Módulos de la ROM que se conservan: vendor y system_dlkm de la base 5.15.137. Que el R10 5.15.216 ya funcione con ellos es evidencia práctica de esa combinación; no demuestra que cualquier compilación 5.15.216 conserve su ABI.
- Kernel fijado: [`d246c8c17548bb1a2756092cabf34d11eedcde8c`](https://github.com/belowzeroiq/kernel_msm-5.15/tree/d246c8c17548bb1a2756092cabf34d11eedcde8c), Linux 5.15.216.
- Imagen KSU del ZIP R10 revisado: SHA-256 `b1953556592d8ccc1ebe081dc341b6625344f36c5ca4844b7c29dc0d00dcd434`.
- Su banner identifica `5.15.216-Zepharo-R10-gd246c8c17548`, Clang/LLD 24.0.0, commit LLVM `c1100cd94b7b89db8c0929192e80aeaea95bc30e`.
- Esa imagen contiene `4.2.0-rc1-7e92d45e@ReSukiSU`. No se sustituirá por otra familia de root al construir ChatGPTKernel.

El ZIP original contiene `Image.ksu`, `Image.noksu`, AnyKernel3 y sus herramientas. No contiene `.ko`, DTB, DTBO, vendor_dlkm ni system_dlkm. Su script declara `do.modules=0`. La nueva entrega debe conservar ese alcance y restringir su comprobación de dispositivo a topaz/tapas.

## Qué decide realmente la carga de módulos

En esta fuente, `CONFIG_MODVERSIONS` no es un simple indicador del nombre del kernel:

1. [`kernel/module.c:1316`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/kernel/module.c#L1316) omite el primer campo de `vermagic` —la cadena `UTS_RELEASE`— si el módulo contiene la sección de versiones. El resto de los atributos debe coincidir.
2. [`check_version()`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/kernel/module.c#L1246) compara el CRC de cada símbolo importado; [`check_modstruct_version()`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/kernel/module.c#L1295) comprueba además `module_layout`.
3. [`include/linux/vermagic.h`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/include/linux/vermagic.h#L42) incorpora SMP, preemption, descarga de módulos, modversions y arquitectura. La imagen R10 contiene `SMP preempt mod_unload modversions aarch64`.

Por ello, usar el sufijo `ChatGPTKernel` no exige falsificar la versión 5.15.137 de los módulos. Tampoco basta con conservar el sufijo o el número 5.15: deben mantenerse símbolos, CRC, estructuras y convenciones de llamada. No se deben eludir estas comprobaciones mediante force-load, eliminación de CRC o parches de `vermagic`.

## Configuración y política de exports

La [`unified_defconfig` fijada](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/arch/arm64/configs/unified_defconfig#L110) selecciona Full LTO, CFI de Clang, módulos, MODVERSIONS y MODULE_SIG_PROTECT. También selecciona [`ANDROID_VENDOR_HOOKS`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/arch/arm64/configs/unified_defconfig#L600).

| Aspecto | Condición de compatibilidad |
| --- | --- |
| ABI de módulos | Mantener `MODULES`, `MODVERSIONS`, SMP, preemption, arquitectura y atributos de `vermagic`; comparar CRC y símbolos requeridos. |
| CFI y compilador | Mantener el esquema CFI/LTO de R10. Cambiar de Full LTO a otra modalidad o de CFI a KCFI no es una optimización inocua para módulos binarios. |
| Estructuras | Conservar reservas KABI y revisar cualquier cambio de estructuras expuestas a módulos. Un CRC compatible no prueba toda interacción semántica de un driver. |
| Hooks Qualcomm | Conservar los hooks Android y sus prototipos, las llamadas correspondientes y los exports utilizados por módulos externos. |
| Exports y trimming | No eliminar símbolos que importen los módulos actuales de vendor/system_dlkm. |
| Firmas | Conservar la política efectiva de R10; no habilitar rechazo obligatorio de firmas ni introducir listas de símbolos protegidos nuevas. |

Las listas [`android/abi_gki_aarch64_qcom`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/android/abi_gki_aarch64_qcom) y [`android/abi_gki_aarch64_xiaomi`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/android/abi_gki_aarch64_xiaomi) existen en la fuente. Eso no prueba que una invocación directa de `make` las utilice.

[`build.config.gki.aarch64`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/build.config.gki.aarch64#L13) declara listas KMI adicionales, enforcement y trimming. **`make unified_defconfig Image` no ejecuta ese wrapper**, sus comprobaciones ABI ni su generación de listas. La configuración y el comando efectivos deben registrar su política de exports. Si se habilita `TRIM_UNUSED_KSYMS`, su whitelist debe existir y cubrir los módulos conservados; el [`Kconfig`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/init/Kconfig#L2374) advierte que, en su ausencia, desaparecen exports sin consumidores internos.

En esta revisión, `android/abi_gki_modules_protected` y `android/abi_gki_modules_exports` contienen solo la cabecera, sin símbolos. Con MODULE_SIG_PROTECT, [`module_sig_check()`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/kernel/module.c#L2978) permite módulos sin firma; las restricciones de acceso/export se aplican a las listas protegidas. No debe confundirse MODULE_SIG_PROTECT con la exigencia de firma válida para todos los drivers.

## Limitación del IKCONFIG publicado

Los dos binarios R10, KSU y no KSU, contienen el mismo bloque IKCONFIG comprimido: SHA-256 `4f035dbeb703406f85d0f27f1671ff82a2b5996edc207cb82368c5cfa446248e`. Ese bloque no declara KSU aunque `Image.ksu` incorpora ReSukiSU.

La causa está identificada en [`kernel/Makefile:151`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/kernel/Makefile#L151): `config_data` se genera desde `arch/arm64/configs/khaje-stock_defconfig`, en lugar de la configuración de compilación. El contenido descomprimido de ambos binarios es idéntico a ese archivo stock: SHA-256 `8755df0767eef8cc10fbc328801a75a3622b82935788b5ac2beb744c691c890f`. Por tanto, tampoco `/proc/config.gz` de R10 revela la configuración efectiva.

La revisión de la nueva compilación debe usar su `.config` final después de `olddefconfig`, sus logs, `include/generated/utsrelease.h`, `Module.symvers` y `vmlinux`. Para que el IKCONFIG de ChatGPTKernel sea útil, su generación debe corregirse para incorporar esa configuración efectiva y comprobarse contra ella. Extraer IKCONFIG de una imagen no sustituye estas evidencias.

## Conservación de KernelSU y de los módulos necesarios

El pin de ReSukiSU es [`7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea`](https://github.com/Baka-SU/BakaSU/tree/7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea); el repositorio anterior ReSukiSU/ReSukiSU redirige al actual Baka-SU/BakaSU. Se fija el commit histórico, sin adoptar el código actual de su rama principal.

- Compilar KSU integrado (`CONFIG_KSU=y`), sin sustituirlo por una entrega exclusivamente LKM.
- Conservar el método de hooks e integración necesario para esa versión y cualquier parche SUSFS realmente utilizado. El IKCONFIG publicado no basta para reconstruirlos.
- Conservar el reconocimiento del manager actual y su política de firmas. El [`Kbuild` fijado](https://github.com/Baka-SU/BakaSU/blob/7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea/kernel/Kbuild#L14) permite excluir el manager; esa opción no debe activarse para esta entrega.
- Registrar versión y commit KSU efectivos. Su Kbuild calcula metadatos con el historial Git, las etiquetas y el nombre de repositorio; un cambio de remoto, un clon incompleto o etiquetas ausentes puede cambiar la versión declarada sin cambiar el código C.
- Mantener intactos los módulos y datos de `/data/adb`, la instalación del manager, NeoZygisk, LSPosed, InstaEclipse y WaEnhancer. Compilar root no certifica que esa cadena se active: debe verificarse en el teléfono.

No se requiere desactivar los módulos necesarios para esta revisión. Su presencia tampoco demuestra que causen la presión de memoria observada.

## Qué puede comprobarse antes de usar el teléfono

- Identidad de fuentes, dependencias, toolchain y hashes; que no se hayan incorporado ramas móviles.
- Compilación completa y configuración final, versión de kernel, presencia de KSU y coherencia del IKCONFIG recién generado.
- Exports y CRC del kernel en `Module.symvers`, incluidos hooks y `module_layout`; comparación con una compilación de referencia realizada con la misma base y cadena de herramientas.
- Si se disponen de los `.ko` exactos de la ROM, comparación de sus imports/CRC y `vermagic` contra los exports de la imagen candidata. Comparar solo contra una referencia reconstruida es evidencia más débil que cotejar los módulos reales.
- Contenido y sintaxis del ZIP. No debe incluir imágenes ni escrituras para DTB, DTBO, vendor, vendor_boot, vendor_dlkm o system_dlkm, ni scripts que modifiquen `/data/adb`.
- Si se aporta una copia del boot actual, desempaquetado/reempaquetado fuera del teléfono para comprobar que DTB, ramdisk, cmdline y demás componentes que deben conservarse no cambian inesperadamente.

No hay en este entorno una colección de los `.ko` exactos del teléfono ni un boot actual. Todavía no puede declararse pasada esa comparación binaria completa.

## Condiciones para una futura prueba en hardware

Antes de instalar una imagen candidata deben estar identificados el dispositivo real topaz/tapas, la ranura y partición de arranque efectivas, el formato/tamaño de boot y una copia recuperable del arranque funcional actual. La copia permite volver a la combinación R10 conocida sin sustituir la ROM o su vendor.

Después de una prueba de arranque autorizada, la evidencia necesaria incluye carga de los mismos drivers y ausencia de nuevos errores de CRC, símbolos desconocidos, firmas o CFI; funcionamiento de pantalla/táctil, Wi-Fi, telefonía/datos, audio, cámara, carga y suspensión; y activación de root, NeoZygisk, LSPosed y las funciones requeridas de InstaEclipse/WaEnhancer.

La mejoría de memoria requiere además mediciones comparables de PSI, zRAM y fluidez con esas funciones activas. Una compilación correcta y un arranque correcto no demuestran por sí solos esa mejoría. Esta revisión no ejecuta un flasheo ni modifica el teléfono.
