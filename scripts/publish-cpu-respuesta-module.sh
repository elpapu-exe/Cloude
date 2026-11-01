#!/usr/bin/env bash
# Publish audited module artifacts; token exists only in this separate CI job.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
CPU_MODULE_DIST=dist/cpu-respuesta-module
CPU_MODULE_VERSION=0.1.0-rc1
CPU_MODULE_TAG="chatgpt-cpu-respuesta-${CPU_MODULE_VERSION}-${GITHUB_SHA:0:12}-${GITHUB_RUN_ID}"
(cd "$CPU_MODULE_DIST" && sha256sum -c SHA256SUMS)
python3 - <<'PY'
import json,os
from pathlib import Path
folder=Path('dist/cpu-respuesta-module')
m=json.loads((folder/'build-manifest.json').read_text())
assert m['version']=='0.1.0-rc1' and m['source_commit']==os.environ['GITHUB_SHA']
assert m['worktree_dirty'] is False and m['skips']==0 and m['tests_run']>0
sums={line.split('  ',1)[1] for line in (folder/'SHA256SUMS').read_text().splitlines()}
assert sums=={p.name for p in folder.iterdir() if p.name!='SHA256SUMS'}
assert sums=={'ChatGPT-CPU-Respuesta-0.1.0-rc1-KSU.zip','ChatGPT-CPU-Respuesta-0.1.0-rc1-sources.zip','build-manifest.json','tests.log'}
PY
if gh release view "$CPU_MODULE_TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  echo 'Refusing to overwrite an existing release.' >&2
  exit 1
fi
CPU_MODULE_NOTES=$(mktemp)
CPU_MODULE_VERIFY=$(mktemp -d)
trap 'rm -f "$CPU_MODULE_NOTES"; rm -rf "$CPU_MODULE_VERIFY"' EXIT
cat > "$CPU_MODULE_NOTES" <<'NOTES'
Módulo experimental KernelSU/ReSukiSU para Redmi Note12 4G TAPAS/topaz, Android13, ARM64 y kernel5.15.

Solo reduce un25% up_rate_limit_us de WALT cuando el valor leído es20001–100000µs y los controles activos tienen identidad y alcance inequívocos. El umbral es una elección experimental, no un valor óptimo publicado. Si la tasa ya es baja, no se cambia. Puede permitir subidas de frecuencia antes a costa de consumo; no hay mejora medida de rendimiento en el teléfono.

No cambia frecuencias mínimas/máximas, gobernador, down_rate_limit_us, GPU, térmicas, SELinux, zRAM, swappiness, LMKD ni módulos personales. SmartPack permanece como gestor de zRAM. No hay un servicio permanente que imponga ajustes repetidamente.

Instala el ZIP terminado en KSU.zip desde KernelSU > Módulos y reinicia. Conserva WhatsApp y tus módulos. Acción inicia una captura de180segundos y no pausa/reactiva el perfil. Espera a que termine el arranque antes de la captura y comparte el TXT ChatGPTKernel-logs indicado. Las instrucciones completas están dentro del ZIP (INSTRUCCIONES.txt).

Para retirar el perfil, desactiva y reinicia. También existe control.sh restore para la restauración inmediata y toggle para pausa/reactivación manual. Solo se restaura en el mismo arranque cuando nodo, gobernador y valor siguen correspondiendo a lo aplicado; se conservan cambios posteriores de otros controladores.

Se entregan fuentes, pruebas, manifest y SHA256SUMS. Antes de publicar se vuelven a descargar todos los assets y se comprueban sus hashes. Las pruebas de scripts usan fixtures Android y no certifican rendimiento en hardware.
NOTES
printf '\nCommit: `%s`.\n' "$GITHUB_SHA" >> "$CPU_MODULE_NOTES"
gh release create "$CPU_MODULE_TAG" "$CPU_MODULE_DIST"/* --repo "$GITHUB_REPOSITORY" \
  --target "$GITHUB_SHA" --draft --prerelease \
  --title "ChatGPT CPU Respuesta $CPU_MODULE_VERSION (experimental)" --notes-file "$CPU_MODULE_NOTES"
gh release download "$CPU_MODULE_TAG" --repo "$GITHUB_REPOSITORY" --dir "$CPU_MODULE_VERIFY"
(cd "$CPU_MODULE_VERIFY" && sha256sum -c SHA256SUMS)
cmp "$CPU_MODULE_DIST/SHA256SUMS" "$CPU_MODULE_VERIFY/SHA256SUMS"
gh release edit "$CPU_MODULE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false --prerelease
gh release view "$CPU_MODULE_TAG" --repo "$GITHUB_REPOSITORY" --json url,assets,isDraft,isPrerelease,targetCommitish
