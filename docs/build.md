# Compilación reproducible por entradas fijadas

Host usado: Debian 13 x86_64, 5 procesos de compilación y límite de 32 GiB de RAM. Full LTO y BTF requieren memoria, espacio y tiempo. Se mantienen para aproximarse a la base R10; no se atribuyen como mejoras nuevas.

```sh
python3 scripts/fetch_host_tools.py
python3 scripts/fetch-sources.py
python3 scripts/prepare-sources.py
bash scripts/configure.sh
bash scripts/build.sh
python3 scripts/verify-artifact.py
python3 scripts/compare-r10-exports.py
python3 scripts/package.py
```

No ejecutes `prepare-sources.py` sobre el árbol ya preparado: aborta para evitar mezclar parches. No hay `curl | bash`, publicación automática ni operaciones sobre el teléfono. Los paquetes Debian se verifican y extraen en `.cache/host`; no se instalan en el sistema. Se necesitan de antemano Git, make, GCC de host, Perl, Python 3.12+, dpkg-deb, OpenSSL y utilidades básicas.

La receta conserva KSU con su historia Git completa: 4442 commits, tag más cercano v4.2.0-rc1, versión numérica 35142. Los hashes de descargas y versiones están en `config/`. SUSFS está fijado a un candidato de la misma versión y fecha, sin prueba de que sea exactamente el commit empleado por el mantenedor de R10.

Fijar las entradas facilita reconstruir la entrega; no se promete identidad bit a bit entre hosts. La clave de firma que el árbol genera automáticamente, las rutas y las herramientas de host pueden modificar el binario. No se distribuyen claves privadas del proceso de construcción.

La configuración efectiva se distribuye con el binario y se incorpora en su IKCONFIG. El nombre de release cambia; las comprobaciones CFI, MODVERSIONS y firmas de módulos permanecen activas. Las comprobaciones KMI del wrapper Android no se ejecutan con `make` directo: no se certifica el ABI contra los módulos reales del teléfono.

El fragmento preserva el orden LSM de la base y añade su Baseband Guard existente. Se usan O2, HZ=300 y Full LTO, como resuelve el defconfig fijado. La opción O3 original depende de ARC y no activa O3 en ARM64. No se altera swappiness, TTL MGLRU, zRAM, LMKD, voltajes ni límites térmicos.

Al desactivar LOCALVERSION_AUTO para un nombre de release fijo, Kconfig desactiva también MODULE_SCMVERSION. Esto afecta metadatos informativos de módulos, sin desactivar MODVERSIONS ni sus CRC.
