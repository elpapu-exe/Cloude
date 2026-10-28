#!/usr/bin/env bash
# GitHub Actions only. Publish only artifacts from the successful audited build job.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${CHATGPT_VERSION:?}" "${GITHUB_RUN_ID:?}"
[[ "$CHATGPT_VERSION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]+$ ]]
CHATGPT_TAG="chatgpt-kernel-${CHATGPT_VERSION}-${GITHUB_SHA:0:12}-${GITHUB_RUN_ID}"
(
  cd dist
  sha256sum -c SHA256SUMS
)
python3 - <<'PY'
import json,os
from pathlib import Path
d=Path('dist')
version=os.environ['CHATGPT_VERSION']
names={line.split('  ',1)[1] for line in (d/'SHA256SUMS').read_text().splitlines()}
assert names=={p.name for p in d.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
audit=json.loads((d/'ci-dist-audit.json').read_text())
assert audit['version']==version
assert audit['all_required_checks_passed'] is True
for name in (f'ChatGPTKernel-{version}-topaz-tapas-A13-KSU.zip',f'ChatGPTKernel-{version}-sources.tar.zst','ChatGPTKernel.config','build-manifest.json','abi-comparison.json','source-archive-audit.json','ci-dist-audit.json'):
    assert name in names and (d/name).stat().st_size>0, name
PY
# A new run uses a new release tag; never replace or clobber someone else's assets.
if gh release view "$CHATGPT_TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  echo "Release already exists: $CHATGPT_TAG; refusing to overwrite it." >&2
  exit 1
fi
CHATGPT_NOTES="$(mktemp)"
{
  printf 'Nueva reconstrucción experimental %s; no es el binario rc3 perdido.\n\n' "$CHATGPT_VERSION"
  printf 'Compilada por GitHub Actions desde el commit `%s`.\n\n' "$GITHUB_SHA"
  printf 'Compilación ARM64, configuración y auditorías de fuentes/artefactos completadas. Sin validación de arranque, rendimiento o temperatura en el teléfono.\n\n'
  cat docs/release-notes.md
} > "$CHATGPT_NOTES"
gh release create "$CHATGPT_TAG" dist/* --repo "$GITHUB_REPOSITORY" \
  --target "$GITHUB_SHA" --draft --prerelease \
  --title "ChatGPT Kernel $CHATGPT_VERSION (experimental)" --notes-file "$CHATGPT_NOTES"
CHATGPT_VERIFY_DIR="$(mktemp -d)"
gh release download "$CHATGPT_TAG" --repo "$GITHUB_REPOSITORY" --dir "$CHATGPT_VERIFY_DIR"
(
  cd "$CHATGPT_VERIFY_DIR"
  sha256sum -c SHA256SUMS
)
cmp dist/SHA256SUMS "$CHATGPT_VERIFY_DIR/SHA256SUMS"
gh release edit "$CHATGPT_TAG" --repo "$GITHUB_REPOSITORY" --draft=false --prerelease
gh release view "$CHATGPT_TAG" --repo "$GITHUB_REPOSITORY" --json url,assets,targetCommitish,isDraft,isPrerelease
{
  printf '### Entrega verificada\n\n'
  printf 'Los assets se descargaron de GitHub y todos sus SHA-256 coinciden antes de publicar.\n\n'
  gh release view "$CHATGPT_TAG" --repo "$GITHUB_REPOSITORY" --json url --jq '.url'
} >> "${GITHUB_STEP_SUMMARY:?}"
rm -f "$CHATGPT_NOTES"
rm -rf "$CHATGPT_VERIFY_DIR"
