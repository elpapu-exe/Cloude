#!/usr/bin/env bash
# Publish only the audited diagnostic files; token exists in this separate CI job.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
REPOSO_DIST=dist/reposo-diagnostic
REPOSO_VERSION=0.1.0-rc3
REPOSO_TAG="chatgpt-reposo-diagnostico-${REPOSO_VERSION}-${GITHUB_SHA:0:12}-${GITHUB_RUN_ID}"
(cd "$REPOSO_DIST" && sha256sum -c SHA256SUMS)
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
folder=Path('dist/reposo-diagnostic')
m=json.loads((folder/'build-manifest.json').read_text())
assert m['module_id']=='chatgpt_reposo_diagnostico' and m['version']=='0.1.0-rc3'
assert m['source_commit']==os.environ['GITHUB_SHA'] and m['worktree_dirty'] is False
assert m['tests_run']>0 and m['failures']==m['errors']==m['skips']==0
assert m['kernel_build_performed'] is False
assert m['collector']['identical_bytes_verified'] is True
assert all(m['zip_audit'].values())
for flag in ('daemon','boot_scripts','timer','wakelock','device_tunable_writes','network_upload'):
    assert m['runtime'][flag] is False,flag
sums={line.split('  ',1)[1] for line in (folder/'SHA256SUMS').read_text().splitlines()}
assert all(p.is_file() for p in folder.iterdir())
assert sums=={p.name for p in folder.iterdir() if p.name!='SHA256SUMS'}
assert sums=={'ChatGPT-Reposo-Diagnostico-0.1.0-rc3-KSU.zip','ChatGPT-Reposo-Diagnostico-0.1.0-rc3-sources.zip','build-manifest.json','tests.log'}
for name,info in m['artifacts'].items():
    p=folder/name
    assert p.stat().st_size==info['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==info['sha256']
PY
if gh release view "$REPOSO_TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  echo 'Refusing to overwrite an existing release.' >&2
  exit 1
fi
REPOSO_NOTES=$(mktemp)
REPOSO_VERIFY=$(mktemp -d)
trap 'rm -f "$REPOSO_NOTES"; rm -rf "$REPOSO_VERIFY"' EXIT
cat > "$REPOSO_NOTES" <<'NOTES'
Diagnóstico de reposo para KernelSU/ReSukiSU. No requiere compilar ni flashear otro kernel.

Actualiza el ZIP terminado en KSU.zip desde KernelSU > Módulos y reinicia si el gestor lo requiere para aplicar la actualización. Mantén Wi-Fi, WhatsApp y tus módulos necesarios; deja desactivados los perfiles experimentales ChatGPT de CPU y memoria durante esta investigación.

Prueba breve de Bluetooth para rc3: activa Bluetooth sin conectar accesorios y espera un minuto. Pulsa Acción para iniciar y espera a que termine. Desactiva Bluetooth, espera unos diez segundos y pulsa Acción de nuevo para finalizar de inmediato. Para esta fase no hace falta esperar diez minutos ni apagar la pantalla. El recolector indica el TXT guardado en Descargas.

rc3 añade lecturas del enlace UART, estado de gestión de energía, parámetros del módulo Bluetooth y posibles procesos asociados, cuando el sistema permite acceder a esos datos. Conserva las lecturas de actividad de procesos, alarmas, wakelocks, UID y estado de red. Son datos de diagnóstico: una coincidencia, un nombre o un contador aislado no demuestra qué componente causa el consumo. Las funciones no disponibles quedan indicadas en el informe.

El módulo termina por completo entre ambas pulsaciones. Sin servicio, tarea de arranque, daemon, temporizador ni wakelock. No cambia zRAM, CPU/GPU, suspensión, seguridad ni protecciones térmicas. Solo escribe el estado privado de la captura y el informe local; no transmite datos. Revisa el informe antes de compartirlo.

El colector instalado se toma directamente del script canónico del proyecto y se comprueba byte por byte. Se entregan fuentes, pruebas, manifest y SHA256SUMS. La publicación se habilita después de descargar de nuevo todos los assets y verificar sus hashes. Las pruebas del host no sustituyen una validación en el dispositivo.
NOTES
printf '\nCommit: `%s`.\n' "$GITHUB_SHA" >> "$REPOSO_NOTES"
gh release create "$REPOSO_TAG" "$REPOSO_DIST"/* --repo "$GITHUB_REPOSITORY" \
  --target "$GITHUB_SHA" --draft --prerelease \
  --title "ChatGPT Reposo Diagnóstico $REPOSO_VERSION" --notes-file "$REPOSO_NOTES"
gh release download "$REPOSO_TAG" --repo "$GITHUB_REPOSITORY" --dir "$REPOSO_VERIFY"
(cd "$REPOSO_VERIFY" && sha256sum -c SHA256SUMS)
cmp "$REPOSO_DIST/SHA256SUMS" "$REPOSO_VERIFY/SHA256SUMS"
gh release edit "$REPOSO_TAG" --repo "$GITHUB_REPOSITORY" --draft=false --prerelease
gh release view "$REPOSO_TAG" --repo "$GITHUB_REPOSITORY" --json url,assets,isDraft,isPrerelease,targetCommitish
