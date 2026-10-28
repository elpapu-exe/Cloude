#!/usr/bin/env bash
# Debian 13 build environment used by GitHub Actions. No GitHub token is passed here.
set -euo pipefail
cd /work
mkdir -p logs
export DEBIAN_FRONTEND=noninteractive
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
/usr/bin/time -v bash scripts/build.sh 2>&1 | tee logs/build.log
python3 scripts/verify-artifact.py
python3 scripts/compare-r10-exports.py
bash scripts/package-sources.sh
# The corresponding-source audit is mandatory, in addition to patch replay.
python3 scripts/ci-audit-dist.py
