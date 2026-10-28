# Revisión de procedencia y cambios de rc3-rebuild1

Esta entrega se identifica como **ChatGPT Kernel 0.1.0-rc3-rebuild1**, una reconstrucción nueva desde el estado publicado `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. En el entorno accesible se encontró rc1 y su serie de tres parches. No se recuperaron el commit local rc2 `b6107b63…`, los cambios sin commit de rc3, su ZIP ni el archivo final de fuentes. Los hashes y validaciones del resumen histórico no son validaciones de esta reconstrucción.

El objetivo sigue siendo corregir defectos concretos y permitir una comparación breve en Redmi Note 12 4G TAPAS de 4 GB con LineageOS 20 Android 13. La candidata conserva la ROM, los módulos necesarios y las protecciones térmicas. No tiene prueba de arranque o rendimiento en el teléfono. La percepción favorable del usuario con una versión anterior no permite atribuir una mejora a cada parche ni a esta nueva candidata.

## Base y límites de procedencia

La base sigue siendo Zepharo R10, Linux 5.15.216, commit `d246c8c17548bb1a2756092cabf34d11eedcde8c`. Las dependencias, identidades y hashes se fijan en [sources.lock.json](../config/sources.lock.json). ReSukiSU utiliza la integración histórica registrada; no se sustituye silenciosamente por una revisión actual. SUSFS 2.3.0 `7af04b08…` sigue siendo un candidato de procedencia razonada cronológicamente, no una identificación demostrada de la fuente exacta usada por el mantenedor de R10.

La correspondencia de fuentes, configuración y binarios requiere las verificaciones de esta ejecución: reaplicación de parches, pruebas, compilación completa, validación de artefactos/exports, auditoría del archivo final de fuentes y SHA256SUMS. La compilación y los CRC coincidentes por sí solos no garantizan arranque ni estabilidad. Los resultados actuales deben consultarse en el manifiesto, los registros y [STATUS.md](../STATUS.md); este documento no sustituye esos resultados.

## Correcciones reconstruidas

| Área | Defecto y alcance | Evidencia y límite |
| --- | --- | --- |
| MGLRU y KProfiles retenidos | MGLRU disponible activo por defecto; configuración IKCONFIG real; bloqueo/notificadores de KProfiles corregidos y retirada de su reescritura adicional de I/O. | Serie original 0001–0003 y revisión previa en [performance-research.md](performance-research.md). Una captura PSI no demuestra una fuga concreta ni culpa de LSPosed. |
| Margen de reclaim | Inicializador de `watermark_scale_factor` de 10 a 64. | Ajuste experimental de margen, no rendimiento garantizado. La ROM puede sobrescribirlo; el valor efectivo se recoge en logs. |
| Tablas SchedHorizon | Sincronizar reemplazo y lectura de tablas dinámicas, límites de índices y parseo/errores. | Necesita pruebas de los helpers reales y compilación. No elige nuevas frecuencias ni convierte Horizon en predeterminado. |
| Caché/límites SchedHorizon | Invalidar demanda rechazada por esperas/hook, preservar actualizaciones forzadas y ordenar publicación de límites. | Antecedentes de contratos en upstream, no cherry-picks literales: [07458f6a](https://github.com/torvalds/linux/commit/07458f6a5171d97511dfbdf6ce549ed2ca0280c7), [8e461a1c](https://github.com/torvalds/linux/commit/8e461a1cb43d69d2fc8a97e61916dce571e6bb31), [cfde542d](https://github.com/torvalds/linux/commit/cfde542df7dd51d26cf667f4af497878ddffd85a), [79443a7e](https://github.com/torvalds/linux/commit/79443a7e9da3c9f68290a8653837e23aba0fa89f). Solo actúa cuando se usa Horizon; schedutil sigue predeterminado. |
| Contabilidad MGLRU | Capturar tipo anon/file de los flags anteriores al CAS exitoso y transmitirlo al batch, sin releer flags cambiantes. | Adaptación del arreglo [766f584c](https://github.com/torvalds/linux/commit/766f584cb6270dadce62c40c0cd4327aff7d531a), “mm/mglru: fix potential generation folio number leak”. No se ha demostrado que causara los ANR de este teléfono. |
| SSG RCU y sysfs | Calcular el resultado de la política dentro de RCU. Rechazar errores de `kstrtoint` antes de modificar valores; conservar clamps válidos. | [Referencia pública de RCU](https://github.com/techyguyperplexable/synthetica_/commit/4706cef306664211aad8823275b6f77e60b9ef33). Tres pruebas ASan/UBSan de funciones/macros reales. Controles negativos sobre la fuente publicada reproducen UAF y aceptación incorrecta de overflow de sysfs. |
| SSG capacidad | Guardar `rq_info_count` privado y comprobar contra la asignación. Usar `tags->nr_tags`, incluidas reservadas; acotar recorridos. | Tres pruebas ASan/UBSan cubren etiquetas reservadas, fallo de asignación, crecimiento/reducción y actualización parcial de hctx. La reconstrucción conserva capacidad al fallar una reasignación y no reduce entre callbacks: un hctx posterior puede fallar cuando otro ya creció. Un control negativo reproduce acceso fuera de asignación en la fuente publicada. |

Las pruebas extraen cuerpos C de las fuentes finales y sustituyen las interfaces del kernel necesarias para modelar intercalados, RCU y errores de asignación. No sustituyen KASAN en un kernel arrancado ni modelan todas las interacciones. No se afirma corregir todos los problemas históricos de SSG: siguen fuera del alcance el tiempo de vida de `blkg` retenido por peticiones y la contabilidad compartida entre hctx.

La candidata no añade cambios de tamaño/compresor de zRAM, LMKD, swappiness, frecuencias/voltajes ni protecciones térmicas. No recrea un dispositivo zRAM temporal al arrancar. La configuración efectiva y la inspección de fuentes deben confirmar estos límites.

## Investigación comunitaria heredada

El resumen del chat anterior registra revisión de repositorios públicos en inglés; no una cobertura de toda la comunidad. ChicKernel stable-7 estaba archivado y usaba Linux 5.15.189; Helios estaba orientado a Android 14/15 sin validación suficiente para A13; palazik aportaba una receta CI tapas 5.15/A13 y romiyusnandar una fuente común topaz/tapas. Esos antecedentes no son una nueva comprobación de su estado actual ni una comparación controlada que pruebe superioridad de rendimiento.

Se mantiene la decisión de no importar indiscriminadamente cambios de `mi_thermald` dependientes de vendor/XML, filtros de kmsg que oculten errores, límites de CPU forzados o backports MGLRU con dependencias ausentes. Algunas correcciones USB/fuel gauge ya estaban presentes en R10 y no deben duplicarse. Los nombres y recomendaciones comunitarias no equivalen a mejoras demostradas para esta ROM.

La siguiente evidencia útil procede de [la comparación de cinco minutos](testing.md), con TikTok oficial, WhatsApp y módulos conservados. Se evaluarán ANR, presión de memoria, tirones percibidos y temperatura antes de proponer más ajustes.
