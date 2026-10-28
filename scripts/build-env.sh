#!/usr/bin/env bash
# Source this file from the project root or from another script.
CHATGPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$CHATGPT_ROOT/.cache/toolchain/bin:$CHATGPT_ROOT/.cache/host/usr/bin:$PATH"
export LD_LIBRARY_PATH="$CHATGPT_ROOT/.cache/host/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export BISON_PKGDATADIR="$CHATGPT_ROOT/.cache/host/usr/share/bison"
export M4="$CHATGPT_ROOT/.cache/host/usr/bin/m4"
export PKG_CONFIG_PATH="$CHATGPT_ROOT/.cache/host/usr/lib/x86_64-linux-gnu/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$CHATGPT_ROOT/.cache/host"
export KBUILD_BUILD_USER=ChatGPT
export KBUILD_BUILD_HOST=kernel-builder
export KBUILD_BUILD_TIMESTAMP='Tue Oct 27 00:00:00 UTC 2026'
export KBUILD_BUILD_VERSION=1
export SOURCE_DATE_EPOCH=1793059200
CHATGPT_MAKE_ARGS=(
  -C "$CHATGPT_ROOT/.cache/linux" O="$CHATGPT_ROOT/out"
  ARCH=arm64 LLVM=1 LLVM_IAS=1
  "HOSTCFLAGS=-O2 -I$CHATGPT_ROOT/.cache/host/usr/include"
  "HOSTLDFLAGS=-L$CHATGPT_ROOT/.cache/host/usr/lib/x86_64-linux-gnu"
)
