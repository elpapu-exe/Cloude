#!/usr/bin/env bash
# Resource provisioning is restricted to disposable Linux GitHub-hosted runners.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
CHATGPT_HOST_PYTHON=/usr/bin/python3
test -x "$CHATGPT_HOST_PYTHON"
CHATGPT_HOSTED=false
if [[ "${RUNNER_ENVIRONMENT:-}" == github-hosted && "$(uname -s)" == Linux ]]; then
  CHATGPT_HOSTED=true
fi
# The compact profile is only enabled after a measured object-only build.
CHATGPT_PROFILE=conservative
if [[ "$CHATGPT_HOSTED" == true ]]; then CHATGPT_PROFILE=hosted_compact; fi
export CHATGPT_CI_MIN_FREE_GIB="${CHATGPT_CI_MIN_FREE_GIB:-$("$CHATGPT_HOST_PYTHON" - "$CHATGPT_PROFILE" <<'PY'
import json,sys
from pathlib import Path
budget=json.loads(Path('config/ci-resources.json').read_text())
profile=budget['profiles'][sys.argv[1]]
if sys.argv[1]=='hosted_compact':
    assert budget['object_measurement']['completed'] is True, 'Missing object-build capacity evidence'
print(profile['minimum_free_workspace_gib'])
PY
)}"
[[ "$CHATGPT_CI_MIN_FREE_GIB" =~ ^[0-9]+$ ]] && (( CHATGPT_CI_MIN_FREE_GIB >= 2 ))
printf 'Configured profile: %s; free workspace reserve: %s GiB\n' "$CHATGPT_PROFILE" "$CHATGPT_CI_MIN_FREE_GIB"
echo "CHATGPT_CI_MIN_FREE_GIB=$CHATGPT_CI_MIN_FREE_GIB" >> "${GITHUB_ENV:?}"
"$CHATGPT_HOST_PYTHON" scripts/ci-resource-report.py --output logs/runner-before.json
bash scripts/ci-capacity-probe.sh | tee logs/runner-disk-before.log
for CHATGPT_TOOL in /usr/bin/python3 git docker; do
  CHATGPT_TOOL_PATH="$(command -v "$CHATGPT_TOOL")"
  printf 'Host tool: %s -> %s\n' "$CHATGPT_TOOL" "$(readlink -f "$CHATGPT_TOOL_PATH")"
done
if [[ "$CHATGPT_HOSTED" == true && "${CHATGPT_CI_CLEAN_SDKS:-true}" == true ]]; then
  # These exact SDK directories are unrelated to this C build inside Debian.
  # Never broaden these paths, touch runner externals, or apply on self-hosted.
  sudo rm -rf -- /usr/local/lib/android /opt/ghc /usr/share/dotnet \
    /opt/hostedtoolcache /usr/local/swift /usr/share/swift \
    /usr/local/share/powershell /home/runner/.rustup /opt/az \
    /opt/microsoft/powershell /opt/microsoft/msedge /usr/lib/jvm \
    /usr/local/share/boost /usr/local/share/chromium /opt/google/chrome
  # Remove only unused images before pulling our pinned Debian image.
  docker system df
  docker image prune --all --force
  docker system df
fi
for CHATGPT_TOOL in /usr/bin/python3 git docker; do
  CHATGPT_TOOL_PATH="$(command -v "$CHATGPT_TOOL")"
  test -x "$CHATGPT_TOOL_PATH"
  printf 'Host tool after cleanup: %s -> %s\n' "$CHATGPT_TOOL" "$(readlink -f "$CHATGPT_TOOL_PATH")"
done
bash scripts/ci-capacity-probe.sh | tee logs/runner-disk-after.log
CHATGPT_SWAP_REQUEST="${CHATGPT_CI_SWAP_GIB:-auto}"
[[ "$CHATGPT_SWAP_REQUEST" =~ ^(auto|[0-9]+)$ ]] || { echo 'Invalid requested swap' >&2; exit 1; }
if [[ "$CHATGPT_HOSTED" == true ]]; then
  CHATGPT_SWAP_PATH="${RUNNER_TEMP:?}/chatgpt-kernel.swap"
  CHATGPT_DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}')"
  test -d "$CHATGPT_DOCKER_ROOT"
  "$CHATGPT_HOST_PYTHON" scripts/ci-resource-report.py --output logs/runner-after-cleanup.json
  CHATGPT_PLAN_ARGS=()
  if [[ "$(stat -c %d "$RUNNER_TEMP")" != "$(stat -c %d "$PWD")" ]]; then
    CHATGPT_PLAN_ARGS+=(--swap-separate-workspace)
  fi
  if [[ "$(stat -c %d "$RUNNER_TEMP")" != "$(stat -c %d "$CHATGPT_DOCKER_ROOT")" ]]; then
    CHATGPT_PLAN_ARGS+=(--swap-separate-docker)
  fi
  "$CHATGPT_HOST_PYTHON" scripts/ci-resource-plan.py \
    --report logs/runner-after-cleanup.json --requested-swap "$CHATGPT_SWAP_REQUEST" \
    --minimum-disk-gib "$CHATGPT_CI_MIN_FREE_GIB" \
    --swap-free-bytes "$(df --output=avail -B1 "$RUNNER_TEMP" | tail -n 1 | tr -d ' ')" \
    --docker-free-bytes "$(df --output=avail -B1 "$CHATGPT_DOCKER_ROOT" | tail -n 1 | tr -d ' ')" \
    "${CHATGPT_PLAN_ARGS[@]}" > logs/resource-plan.json
  cat logs/resource-plan.json
  CHATGPT_SWAP_GIB="$("$CHATGPT_HOST_PYTHON" -c 'import json; print(json.load(open("logs/resource-plan.json"))["extra_swap_gib"])')"
  if (( CHATGPT_SWAP_GIB > 0 )); then
    test ! -e "$CHATGPT_SWAP_PATH"
    echo "CHATGPT_CREATED_SWAP=$CHATGPT_SWAP_PATH" >> "${GITHUB_ENV:?}"
    sudo fallocate -l "${CHATGPT_SWAP_GIB}G" "$CHATGPT_SWAP_PATH"
    sudo chmod 600 "$CHATGPT_SWAP_PATH"
    sudo mkswap "$CHATGPT_SWAP_PATH"
    sudo swapon "$CHATGPT_SWAP_PATH"
  fi
fi
# Re-measure actual usable swap, including cgroup limits, after provisioning.
"$CHATGPT_HOST_PYTHON" scripts/ci-resource-report.py --enforce --output logs/runner-resources.json
docker version --format '{{.Server.Version}}' | tee logs/docker-version.txt
