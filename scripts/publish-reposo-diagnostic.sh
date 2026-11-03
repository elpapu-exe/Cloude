#!/usr/bin/env bash
# Publish only the audited diagnostic files; token exists in this separate CI job.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
REPOSO_DIST=dist/reposo-diagnostic
REPOSO_VERSION=0.1.0-rc2
REPOSO_TAG="chatgpt-reposo-diagnostico-${REPOSO_VERSION}-${GITHUB_SHA:0:12}-${GITHUB_RUN_ID}"
(cd "$REPOSO_DIST" && sha256sum -c SHA256SUMS)
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
folder=Path('dist/reposo-diagnostic')
m=json.loads((folder/'build-manifest.json').read_text())
assert m['module_id']=='chatgpt_reposo_diagnostico' and m['version']=='0.1.0-rc2'
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
assert sums=={'ChatGPT-Reposo-Diagnostico-0.1.0-rc2-KSU.zip','ChatGPT-Reposo-Diagnostico-0.1.0-rc2-sources.zip','build-manifest.json','tests.log'}
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

Instala el ZIP terminado en KSU.zip desde KernelSU > Módulos. Si no aparece Acción, reinicia una vez. Pulsa Acción para iniciar, apaga la pantalla unos diez minutos y pulsa Acción otra vez para finalizar. El recolector indica el TXT que guarda en Descargas. Conserva WhatsApp y los módulos que necesitas.

rc2 amplía las instantáneas con actividad de procesos y, cuando el sistema permite leerlos, datos de alarmas, wakelocks y UID, además del estado de red. Estos datos ayudan a investigar qué mantiene activo el teléfono; un contador o nombre aislado no demuestra la causa del consumo. Las funciones no disponibles quedan indicadas en el informe.

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
