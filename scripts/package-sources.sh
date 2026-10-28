#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/build-env.sh"
cd "$CHATGPT_ROOT"
test -s out/arch/arm64/boot/Image
cp out/.config config/effective.config
mkdir -p dist
# No nested Git history, build output, toolchain or credentials in this archive.
tar --sort=name --mtime='2026-10-28 00:00:00 UTC' \
  --owner=0 --group=0 --numeric-owner \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  -I 'zstd -T2 -3' -cf dist/ChatGPTKernel-0.1.0-rc4-sources.tar.zst \
  README.md STATUS.md .gitignore .gitattributes .github config docs patches scripts tests installer \
  .cache/linux .cache/kernelsu .cache/baseband-guard .cache/susfs .cache/prepared.json \
  .cache/source-receipts out/build-manifest.json
python3 scripts/audit-source-archive.py
python3 scripts/package.py
(cd dist && sha256sum -c SHA256SUMS)
