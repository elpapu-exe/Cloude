#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/build-env.sh"
cd "$CHATGPT_ROOT"
test -s out/arch/arm64/boot/Image
cp out/.config config/effective.config
mkdir -p dist
tar --sort=name --mtime='2026-10-23 00:00:00 UTC' \
  --owner=0 --group=0 --numeric-owner \
  --exclude='*/__pycache__' --exclude='*.pyc' \
  -I 'zstd -T2 -3' -cf dist/ChatGPTKernel-0.1.0-rc1-sources.tar.zst \
  README.md STATUS.md .gitignore .gitattributes config docs patches scripts tests installer \
  .cache/linux .cache/kernelsu .cache/baseband-guard .cache/susfs .cache/prepared.json
python3 scripts/package.py
