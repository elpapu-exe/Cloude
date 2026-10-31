#!/usr/bin/env bash
# Publish audited module artifacts; token exists only in this separate CI job.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
FLUIDEZ_DIST=dist/fluidez-module
FLUIDEZ_VERSION=0.1.0-rc1
FLUIDEZ_TAG="chatgpt-fluidez-${FLUIDEZ_VERSION}-${GITHUB_SHA:0:12}-${GITHUB_RUN_ID}"
(cd "$FLUIDEZ_DIST" && sha256sum -c SHA256SUMS)
python3 - <<'PY'
import json,os
from pathlib import Path
folder=Path('dist/fluidez-module')
m=json.loads((folder/'build-manifest.json').read_text())
assert m['version']=='0.1.0-rc1' and m['source_commit']==os.environ['GITHUB_SHA']
assert m['worktree_dirty'] is False and m['skips']==0 and m['tests_run']>0
sums={line.split('  ',1)[1] for line in (folder/'SHA256SUMS').read_text().splitlines()}
assert sums=={p.name for p in folder.iterdir() if p.name!='SHA256SUMS'}
assert sums=={'ChatGPT-Fluidez-Memoria-0.1.0-rc1-KSU.zip','ChatGPT-Fluidez-Memoria-0.1.0-rc1-sources.zip','build-manifest.json','tests.log'}
PY
if gh release view "$FLUIDEZ_TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  echo 'Refusing to overwrite an existing release.' >&2
  exit 1
fi
FLUIDEZ_NOTES=$(mktemp)
FLUIDEZ_VERIFY=$(mktemp -d)
trap 'rm -f "$FLUIDEZ_NOTES"; rm -rf "$FLUIDEZ_VERIFY"' EXIT
cat > "$FLUIDEZ_NOTES" <<'NOTES'
Módulo experimental KernelSU/ReSukiSU para Redmi Note12 4G TAPAS/topaz, Android13, ARM64 y kernel5.15. No requiere recompilar o flashear el kernel.

Prueba dos controles: activar el core MGLRU si está apagado y elevar watermark_scale_factor a64 si era menor. 64 es una elección experimental del proyecto, no una recomendación universal. Puede mejorar o empeorar la respuesta y todavía no hay medición de rendimiento en el teléfono.

Instala el ZIP terminado en KSU.zip desde KernelSU > Módulos y reinicia. Tras iniciar Android, espera un minuto. Conserva WhatsApp y los módulos necesarios. Acción pausa/restaura o reactiva, y exporta un informe TXT en Descargas. Si empeora, pausa o desactiva y reinicia. Desactivar por sí solo no restaura inmediatamente.

Conserva tamaño/compresor de zRAM, swappiness, LMKD, CPU/GPU, protecciones térmicas y SELinux. Sin montajes, servicio permanente, limpieza de cachés, cierre de apps ni subida de datos. Las instrucciones completas están dentro del ZIP (INSTRUCCIONES.txt).

Se entregan fuentes, pruebas, manifest y SHA256SUMS. La publicación solo se habilita después de descargar de nuevo todos los assets y comprobar sus hashes. Las pruebas usan archivos/comandos Android simulados y no certifican rendimiento en hardware.
NOTES
printf '\nCommit: `%s`.\n' "$GITHUB_SHA" >> "$FLUIDEZ_NOTES"
gh release create "$FLUIDEZ_TAG" "$FLUIDEZ_DIST"/* --repo "$GITHUB_REPOSITORY" \
  --target "$GITHUB_SHA" --draft --prerelease \
  --title "ChatGPT Fluidez Memoria $FLUIDEZ_VERSION (experimental)" --notes-file "$FLUIDEZ_NOTES"
gh release download "$FLUIDEZ_TAG" --repo "$GITHUB_REPOSITORY" --dir "$FLUIDEZ_VERIFY"
(cd "$FLUIDEZ_VERIFY" && sha256sum -c SHA256SUMS)
cmp "$FLUIDEZ_DIST/SHA256SUMS" "$FLUIDEZ_VERIFY/SHA256SUMS"
gh release edit "$FLUIDEZ_TAG" --repo "$GITHUB_REPOSITORY" --draft=false --prerelease
gh release view "$FLUIDEZ_TAG" --repo "$GITHUB_REPOSITORY" --json url,assets,isDraft,isPrerelease,targetCommitish
