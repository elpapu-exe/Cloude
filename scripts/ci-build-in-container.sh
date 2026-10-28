#!/usr/bin/env bash
# Run one visible CI phase in the same pinned Debian container. No GitHub token.
set -euo pipefail
cd /work
mkdir -p logs
export DEBIAN_FRONTEND=noninteractive
export CHATGPT_TEST_SOURCE_ROOT=/work/.cache/linux
CHATGPT_PHASE=${1:?Expected one phase: setup, objects, link or audit}
[[ "$#" -eq 1 ]] || { echo 'Exactly one CI phase is required.' >&2; exit 2; }
case "$CHATGPT_PHASE" in setup|objects|link|audit) ;; *) echo 'Unknown CI phase.' >&2; exit 2;; esac
CHATGPT_CPU_COUNT=$(getconf _NPROCESSORS_ONLN)
CHATGPT_JOB_LIMIT=${CHATGPT_JOBS:-$CHATGPT_CPU_COUNT}
[[ "$CHATGPT_JOB_LIMIT" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid build job count.' >&2; exit 2; }
(( CHATGPT_JOB_LIMIT <= CHATGPT_CPU_COUNT )) || CHATGPT_JOB_LIMIT=$CHATGPT_CPU_COUNT
(( CHATGPT_JOB_LIMIT <= 5 )) || CHATGPT_JOB_LIMIT=5
export CHATGPT_JOBS=$CHATGPT_JOB_LIMIT
printf 'CI phase: %s; parallel jobs: %s; tested Linux source: %s\n' \
  "$CHATGPT_PHASE" "$CHATGPT_JOBS" "$CHATGPT_TEST_SOURCE_ROOT"

case "$CHATGPT_PHASE" in
  setup)
    apt-get update
    apt-get install -y --no-install-recommends \
      ca-certificates git make gcc g++ perl python3 dpkg-dev libssl-dev openssl \
      zstd curl xz-utils file time libbpf1 liblz4-1 libxxhash0 libzstd-dev \
      zlib1g-dev liblzma-dev libreadline8t64
    git config --global --add safe.directory /work
    git rev-parse HEAD > logs/source-commit.txt
    dpkg-query -W -f='${binary:Package}\t${Version}\n' > logs/container-packages.txt
    python3 scripts/ci-resource-report.py --enforce --output logs/container-resources.json
    python3 scripts/fetch_host_tools.py
    python3 scripts/fetch-sources.py
    python3 scripts/prepare-sources.py
    bash scripts/configure.sh
    python3 - <<'PYCODE'
import hashlib,json
from pathlib import Path
budget=json.loads(Path('config/ci-resources.json').read_text())['object_measurement']
assert hashlib.sha256(Path('out/.config').read_bytes()).hexdigest()==budget['effective_config_sha256'], 'Effective config differs from the measured workload'
assert hashlib.sha256(Path('config/sources.lock.json').read_bytes()).hexdigest()==budget['source_pins_sha256'], 'Source pins differ from the measured workload'
PYCODE
    ;;
  objects)
    test -s .cache/prepared.json
    python3 scripts/verify-config.py
    # descend compiles the normal Kbuild object prerequisites without Full LTO.
    python3 scripts/ci-guard-space.py --phase objects --minimum-free-gib 2 \
      --log logs/disk-guard-objects.jsonl -- \
      /usr/bin/time -v bash -euo pipefail -c \
      'source scripts/build-env.sh; make "${CHATGPT_MAKE_ARGS[@]}" -j"$CHATGPT_JOBS" descend' \
      2>&1 | tee logs/object-build.log
    ;;
  link)
    test -s .cache/prepared.json
    # build.sh keeps Image, Full LTO, CFI and the locked effective configuration.
    # Kbuild reuses the object phase; the guard fails before/during disk exhaustion.
    python3 scripts/ci-guard-space.py --phase link --minimum-free-gib 2 \
      --log logs/disk-guard-link.jsonl -- \
      /usr/bin/time -v bash scripts/build.sh 2>&1 | tee logs/build.log
    ;;
  audit)
    python3 scripts/verify-artifact.py
    python3 scripts/compare-r10-exports.py
    bash scripts/package-sources.sh
    # Includes all required release regressions against the actual prepared Linux tree,
    # plus mandatory final corresponding-source and checksum audits.
    python3 scripts/ci-audit-dist.py
    ;;
esac
