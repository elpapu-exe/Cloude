#!/usr/bin/env bash
# Runs on the GitHub runner host; never changes the connected phone.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
python3 scripts/ci-resource-report.py --output logs/runner-before.json
if [[ "${RUNNER_ENVIRONMENT:-}" == github-hosted && "${CHATGPT_CI_CLEAN_SDKS:-true}" == true ]]; then
  # Disposable hosted runner only. These SDKs are unrelated to the C/ARM64 build.
  sudo rm -rf /usr/local/lib/android /opt/ghc /usr/share/dotnet
fi
CHATGPT_SWAP_GIB="${CHATGPT_CI_SWAP_GIB:-32}"
[[ "$CHATGPT_SWAP_GIB" =~ ^[0-9]+$ ]] || { echo 'Invalid swap GiB' >&2; exit 1; }
if [[ "$CHATGPT_SWAP_GIB" -gt 0 && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]]; then
  # Self-hosted machines must have their own swap provisioned by their operator.
  # Retain existing swap; an extra file is created only if aggregate headroom is low.
  CHATGPT_AVAILABLE="$(python3 scripts/ci-resource-report.py | python3 -c 'import json,sys; print(json.load(sys.stdin)["available_memory_swap_bytes"])')"
  if (( CHATGPT_AVAILABLE < 36 * 1024 * 1024 * 1024 )); then
    CHATGPT_SWAP_PATH="${RUNNER_TEMP:?}/chatgpt-kernel.swap"
    CHATGPT_FREE_BYTES="$(df --output=avail -B1 "$RUNNER_TEMP" | tail -n 1 | tr -d ' ')"
    CHATGPT_REQUIRED_BYTES=$(( (CHATGPT_SWAP_GIB + 45) * 1024 * 1024 * 1024 ))
    if (( CHATGPT_FREE_BYTES < CHATGPT_REQUIRED_BYTES )); then
      echo 'Insufficient space for requested swap plus 45 GiB build headroom.' >&2
      python3 scripts/ci-resource-report.py --output logs/runner-resources.json
      exit 1
    fi
    test ! -e "$CHATGPT_SWAP_PATH"
    sudo fallocate -l "${CHATGPT_SWAP_GIB}G" "$CHATGPT_SWAP_PATH"
    sudo chmod 600 "$CHATGPT_SWAP_PATH"
    sudo mkswap "$CHATGPT_SWAP_PATH"
    sudo swapon "$CHATGPT_SWAP_PATH"
    echo "CHATGPT_CREATED_SWAP=$CHATGPT_SWAP_PATH" >> "${GITHUB_ENV:?}"
  fi
fi
python3 scripts/ci-resource-report.py --enforce --output logs/runner-resources.json
docker version --format '{{.Server.Version}}' | tee logs/docker-version.txt
