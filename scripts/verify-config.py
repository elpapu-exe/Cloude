#!/usr/bin/env python3
"""Fail before compilation if required security/compatibility choices disappear."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config = (root / "out/.config").read_text()
required = (
    "ARM64", "SMP", "PREEMPT", "SHADOW_CALL_STACK", "ANDROID_VENDOR_HOOKS", "MODULES", "MODVERSIONS", "MODULE_SIG", "MODULE_SIG_PROTECT",
    "CFI_CLANG", "LTO_CLANG_FULL", "DEBUG_INFO_BTF", "LRU_GEN",
    "LRU_GEN_ENABLED", "PSI", "KSU", "KSU_SUSFS", "KSU_MULTI_MANAGER_SUPPORT",
    "BBG", "THERMAL", "IKCONFIG", "IKCONFIG_PROC", "CC_OPTIMIZE_FOR_PERFORMANCE",
)
for name in required:
    assert f"CONFIG_{name}=y\n" in config, f"Required setting missing: {name}"
for name in ("KSU_DISABLE_MANAGER", "KSU_DISABLE_POLICY", "KSU_TRACEPOINT_HOOK", "BBG_BLOCK_BOOT", "MODULE_SIG_FORCE", "TRIM_UNUSED_KSYMS"):
    assert f"CONFIG_{name}=y\n" not in config, f"Unexpected setting: {name}"
assert 'CONFIG_LOCALVERSION="-ChatGPTKernel-0.1.0-rc3-rebuild1"\n' in config
assert 'baseband_guard' in next(x for x in config.splitlines() if x.startswith('CONFIG_LSM='))
print("Verified candidate configuration: MGLRU, thermal, KSU, CFI and module protections")
