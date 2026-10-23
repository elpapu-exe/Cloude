#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/build-env.sh"
mkdir -p "$CHATGPT_ROOT/out" "$CHATGPT_ROOT/logs"
make "${CHATGPT_MAKE_ARGS[@]}" unified_defconfig
cp "$CHATGPT_ROOT/out/.config" "$CHATGPT_ROOT/out/reference.config"
KCONFIG_CONFIG="$CHATGPT_ROOT/out/.config" "$CHATGPT_ROOT/.cache/linux/scripts/kconfig/merge_config.sh" -m -O "$CHATGPT_ROOT/out" "$CHATGPT_ROOT/out/.config" "$CHATGPT_ROOT/config/chatgpt.config"
make "${CHATGPT_MAKE_ARGS[@]}" olddefconfig
python3 "$CHATGPT_ROOT/scripts/verify-config.py"
