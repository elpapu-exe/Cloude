#!/usr/bin/env bash
# Read-only disk inventory. File names and sizes only; no credential contents.
set -euo pipefail
cd "$(dirname "$0")/.."
printf 'Capacity inventory UTC: %s\n' "$(date -u +%FT%TZ)"
python3 scripts/ci-resource-report.py
df -hT
if command -v lsblk >/dev/null 2>&1; then
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
fi
if command -v findmnt >/dev/null 2>&1; then
  for CHATGPT_PATH in "$PWD" "${RUNNER_TEMP:-/tmp}" /mnt /tmp; do
    if [[ -e "$CHATGPT_PATH" ]]; then
      findmnt --target "$CHATGPT_PATH" --output TARGET,SOURCE,FSTYPE,SIZE,AVAIL,OPTIONS
    fi
  done
fi
CHATGPT_PRIVILEGE=()
if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  CHATGPT_PRIVILEGE=(sudo -n)
fi
for CHATGPT_PATH in \
  /usr/local/lib/android /opt/ghc /usr/share/dotnet /opt/hostedtoolcache \
  /usr/local/swift /usr/share/swift /usr/local/go /opt/az \
  /usr/local/share/powershell /home/runner/.rustup /home/runner/.cache \
  /var/lib/docker /opt/microsoft /home/runner/work /mnt; do
  if [[ -e "$CHATGPT_PATH" ]]; then
    "${CHATGPT_PRIVILEGE[@]}" du -xsh -- "$CHATGPT_PATH" 2>&1 || true
  fi
done
