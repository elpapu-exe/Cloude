# ChatGPT Kernel 0.1.0-rc5 — en preparación

Fuentes candidatas para Redmi Note 12 4G TAPAS/topaz y Android 13. No hay ZIP rc5 publicado todavía ni una mejora de rendimiento medida en el teléfono. La entrega anterior rc4 permanece disponible con sus propios hashes.

Cambios respecto a rc4:

- MGLRU: protege mejor la caché reutilizada mediante colocación de generaciones, referencias saturadas y estado de refault (upstream 081488051d28).
- Reclaim: retira el filtro CMA que puede prolongar recorridos del LRU clásico y provocar promociones innecesarias en MGLRU (upstream bfe0857c20c6). Se conservan los filtros de zona y los demás requisitos de aislamiento.
- Recolector v6 de solo lectura: identifica drivers/tasas reales, colas de almacenamiento y señales adicionales de memoria para elegir los ajustes siguientes.

Los cambios anteriores de rc4 se mantienen. El inicializador watermark sigue en 10; no se han decidido cambios de zRAM, compresor, swappiness, LMKD, frecuencias o voltajes. La ROM puede sobrescribir parámetros tras el arranque. No se desactivan protecciones térmicas, CFI, Full LTO, SCS, BTF o MODVERSIONS.

Las pruebas de helpers reales verifican contratos de las correcciones, no FPS, batería o arranque. La procedencia exacta del SUSFS histórico de R10 sigue sin demostrarse y los límites anteriores de SSG/ABI permanecen documentados. Los resultados definitivos deben corresponder al manifest y los logs de una futura ejecución propia de rc5, sin reutilizar la validación de rc4.

Antes de instalar una entrega verificada, guarda el boot funcional fuera del teléfono y consulta la guía de instalación/recuperación. La comparación conserva TikTok oficial, WhatsApp y los módulos del usuario.

Comprobaciones locales: 93 pruebas obligatorias sin fallos ni omisiones y reaplicación exacta de 18 parches sobre 40 archivos finales, con snapshots Linux/KSU/BBG coincidentes. El enlace Full LTO, la comparación de exports/CRC del nuevo binario y la evaluación en hardware siguen pendientes.
