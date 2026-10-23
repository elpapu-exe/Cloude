#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/build-env.sh"
python3 "$CHATGPT_ROOT/scripts/verify-config.py"
make "${CHATGPT_MAKE_ARGS[@]}" -j"${CHATGPT_JOBS:-5}" Image
