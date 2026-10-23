# Source and build provenance

This audit records the public evidence used to prepare ChatGPT Kernel. It does
not certify that a new build boots, preserves the vendor module ABI, or improves
performance. A successful compilation is a separate result from device testing.

## Baseline selected

The reference is the user's working Zepharo R10 on Android 13, rather than a new
kernel family or a reconstruction of the old ROM's stock kernel.

| Item | Pinned reference | Evidence |
| --- | --- | --- |
| Kernel source | `d246c8c17548bb1a2756092cabf34d11eedcde8c` | [Source tree](https://github.com/belowzeroiq/kernel_msm-5.15/tree/d246c8c17548bb1a2756092cabf34d11eedcde8c); matches the `gd246c8c17548` suffix in the user's uname and the public R10 binary. |
| Kernel release | `5.15.216-Zepharo-R10-gd246c8c17548` | Extracted from the public `Image.ksu` Linux version banner. |
| Reference ZIP | `Anykernel3_Zepharo_R10_2026-09-14.zip` | [Maintainer release](https://github.com/topnotchfreaks/kernel_msm-5.15/releases/tag/ZEPHARO). The release page is a collection of multiple versions; its tag date alone is not the R10 build date. |
| ZIP SHA-256 | `b5f536b1c624172d4e44ccdacde56205966b8a7522f319d94778cc8ac464fc80` | Calculated from the downloaded reference ZIP. |
| KSU Image SHA-256 | `b1953556592d8ccc1ebe081dc341b6625344f36c5ca4844b7c29dc0d00dcd434` | Calculated from the ZIP member `Image.ksu`, 50,141,696 bytes. |
| Non-KSU Image SHA-256 | `5cd755d1163285f1aa74181debb6cbb674a500d22b1b380ccb2c720b7379ac4d` | Calculated from the ZIP member `Image.noksu`, 49,940,992 bytes. |

The KSU binary reports compilation at **2026-09-14 12:52:48 UTC**, Cirrus clang
24.0.0 and LLD 24.0.0, both identifying LLVM revision
`c1100cd94b7b89db8c0929192e80aeaea95bc30e`. Its embedded root string is
`v4.2.0-rc1-7e92d45e@ReSukiSU`; its SUSFS version string is `v2.3.0`.

The downloaded binary is a comparison reference. Renaming or repackaging it
would not constitute a newly compiled or optimized ChatGPT Kernel.

## Historical build recipe

[Advanced Build #33, run 34844072544](https://github.com/topnotchfreaks/kernel_msm-5.15/actions/runs/34844072544)
started at **2026-09-14 12:50:59 UTC**, used builder revision
`51e26a59c10a0199c1f0d1861c78107c35698c85`, and contains KSU/non-KSU build jobs
and a packaging job. Its timing matches the public R10 binary. The
[workflow at that revision](https://github.com/topnotchfreaks/kernel_msm-5.15/blob/51e26a59c10a0199c1f0d1861c78107c35698c85/.github/workflows/advanced_build.yml)
is a stronger reference than today's moving `builder` branch.

The workflow's `custom-tools` path selected the latest Greenforce archive at
build time. Its alternative AOSP toolchain path used a different compiler. The
matching Cirrus banner therefore supports the custom-toolchain path. Public
run metadata does not expose the selected workflow inputs or an archive digest
from the original CI log; those details are not claimed as proven.

The historical workflow is evidence to audit, not a script to run unchanged.
It contains moving dependency references, network-dependent setup, and optional
publication/notification operations that are unnecessary for a local build.

## Configuration and compilation flags

At the pinned source revision,
[`build.config.gki`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/build.config.gki)
selects `unified_defconfig` directly. Do not replace this with generic
`gki_defconfig` merely because the device uses GKI.

The pinned
[`unified_defconfig`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/arch/arm64/configs/unified_defconfig)
contains these relevant baseline settings:

| Setting | Baseline value / implication |
| --- | --- |
| `CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE_O3` | `y`; the pinned Makefile maps this to `-O3`. |
| `CONFIG_LTO_CLANG_FULL` | `y`; full LTO is already part of R10, not a new optimization. |
| `CONFIG_CFI_CLANG`, `CONFIG_SHADOW_CALL_STACK` | Both `y`; preserve their ABI and security implications. |
| `CONFIG_MODULES`, `CONFIG_MODVERSIONS` | Both `y`; vendor module symbol compatibility must be checked. |
| `CONFIG_ANDROID_VENDOR_HOOKS` | `y`. |
| `CONFIG_GKI_HACKS_TO_FIX` | `y`; an existing baseline dependency, not a newly added feature. |
| `CONFIG_KPROFILES`, `CONFIG_KP_DEFAULT_MODE` | Enabled, default profile `3`. Runtime changes made on the phone are separate from this compile default. |
| `CONFIG_AUTO_KPROFILES` | Not enabled in this defconfig. |
| `CONFIG_CPU_FREQ_GOV_SCHEDHORIZON` | `y`. |
| `CONFIG_LRU_GEN` | `y`; compiled support alone does not prove the phone's runtime enabled bitmap. |
| `CONFIG_IKCONFIG`, `CONFIG_IKCONFIG_PROC` | Both `y`, but see the inconsistency below. |

[`build.config.common`](https://github.com/belowzeroiq/kernel_msm-5.15/blob/d246c8c17548bb1a2756092cabf34d11eedcde8c/build.config.common)
sets `LLVM=1`, KMI generation `8`, and the Android common-kernel compilation
define. Its toolchain constants still name AOSP clang `r450784e`; that name does
not match the R10 binary's actual compiler. A local build must deliberately
select the pinned Cirrus tools instead of silently following that stale name.

### Embedded IKCONFIG is not the effective R10 configuration

The reference Image's embedded compressed configuration reports older compiler
metadata and omits KProfiles/Schedhorizon settings even though those functions
are present in the binary and in the pinned source defconfig. It therefore
cannot be treated as a complete, reliable recipe for reproducing R10.
The cause is visible in the pinned `kernel/Makefile`: its `config_data` target
reads `arch/arm64/configs/khaje-stock_defconfig` instead of the generated build
configuration. This is deliberate stock-configuration embedding, not evidence
that those stock settings compiled the running kernel. A correction should be
recorded separately from performance changes.

Record and retain the newly generated build `.config` after Kconfig resolution,
including KSU/SUSFS additions. Audit any unexpected changes from the pinned
defconfig and declared fragments. Do not describe an inferred configuration as
the original maintainer's fully recovered effective `.config`.

## Dependency pins and confidence

Detailed file URLs and hashes are recorded in [dependency-pins.json](dependency-pins.json)
and [dependency-source-notes.md](dependency-source-notes.md). The root project's
machine-readable build inputs belong in `config/sources.lock.json`.

| Component | Pin | Confidence and remaining distinction |
| --- | --- | --- |
| Cirrus/Greenforce toolchain | Release `20260912`; SHA-256 `33dc3bfa3a5c9c56797f218de8a33d1a85719c3219cebfd5818bcba9933ea961` | Official release asset digest; its declared LLVM revision matches R10 exactly. This was the latest release before the R10 build, consistent with the historical workflow. Earlier September assets share the same LLVM revision, so identity of the originally downloaded archive is not independently logged here. |
| ReSukiSU | `7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea` | Exact match to the binary's embedded short revision. GitHub now redirects the old ReSukiSU repository to Baka-SU/BakaSU; the historical snapshot retains the ReSukiSU identity. |
| SUSFS 2.3.0 | `7af04b08f86a5f811cbea28805f96d52368e005f`, `gki-android13-5.15` history | Latest identified commit before the reference build; its header reports `v2.3.0`. Chronologically supported candidate, not a binary-proven exact source identity. |

Toolchain sources:
[release](https://github.com/greenforce-project/greenforce_clang/releases/tag/20260912),
[archive](https://github.com/greenforce-project/greenforce_clang/releases/download/20260912/gf-clang-24.0.0-20260912.tar.gz),
[official asset digest](https://github.com/greenforce-project/greenforce_clang/releases/expanded_assets/20260912).
The archive must pass its digest check; compiler and linker banners must then
be compared with the recorded LLVM revision.

ReSukiSU's historical Kbuild derives its version code from Git history and its
name from tags and the commit. Preserve that metadata deliberately; a source
tarball or a depth-one clone alone does not preserve `git rev-list --count` or
`git describe` output. The `v4.2.0-rc1` tag points to another commit and must not
replace the exact `7e92d45e` pin. Avoid the Kbuild's implicit unshallow fetch by
preparing the required history before an offline build.
The prepared full-history checkout was subsequently verified locally at that
exact HEAD: `git rev-list --count HEAD` returns `4442` and
`git describe --abbrev=0 --tags` returns `v4.2.0-rc1`. The historical formula
therefore gives KSU version code **35142** (`30000 + 4442 + 700`). These are
locally checked metadata, rather than the earlier inference from GitHub's UI.

The pinned R10 source does not itself contain the added SUSFS implementation
and hooks. Those were supplied during the maintainer's build. The chosen
SUSFS kernel patch and replacement files must be captured by immutable revision
and digest. ReSukiSU already has SUSFS support; the separate patch intended for
official KernelSU must not be applied automatically to this fork. Patch
application and integration checks are build results still to verify.

## Packaging and vendor compatibility boundary

The reference AnyKernel script targets `boot`, detects the active slot, lists
`topaz`/`tapas`, allows Android 13–17, and sets `do.modules=0`. Its normal paths
read the installed boot image and repack it around the selected kernel. The
reference ZIP contains no replacement DTB, DTBO, vendor ramdisk, or vendor
module bundle. This explains why preparing a replacement `Image` and installer
does not require uploading the ROM ZIP or the phone's `boot.img`.

AnyKernel's device-name and Android-version checks are packaging checks. They
do not validate kernel/vendor KMI, module CRCs, hardware operation, KSU manager
compatibility, or application stability. Preserve the installed vendor
components and verify the new build's symbol/version compatibility. Keeping
the old release name alone does not make a changed kernel ABI compatible.
Conversely, the pinned `kernel/module.c` `same_magic()` implementation ignores
the initial kernel-release field when a module carries symbol CRCs. A new
ChatGPT Kernel release label is therefore not, by itself, evidence of a module
ABI break; CRCs, `module_layout`, the remaining vermagic fields and relevant
configuration still require review.

Reference installer member hashes, calculated from the public R10 ZIP:

```text
anykernel.sh
2c7184a927245bd9e47290afe040d453d3dceb439c1870a4adb91191111a19d0

tools/ak3-core.sh
d49fa5f821acc82060047504ec405192b641b0265efd9f6cc3dcc6b75bec4848
```

A local backup of the phone's current boot remains necessary before an eventual
device trial; it need not be uploaded to this repository. No host-side build or
packaging check substitutes for that recovery path.

## Review gates

1. Verify every locked source/toolchain digest and preserve dependency version
   metadata; do not silently advance to `main` or `latest`.
2. Generate and archive the resolved baseline configuration and full build log.
3. Produce a newly compiled baseline with the declared KSU/SUSFS integration;
   compare version metadata, compiler identity, artifact format/size and module
   ABI evidence with the reference before performance changes.
4. Keep any proposed optimization separate and justified by source evidence.
   Full LTO and `-O3` are already baseline settings. Do not claim extra gains
   merely for retaining them.
5. Report build, static validation and device validation separately. Until the
   phone has run the resulting build, startup, thermal behavior, battery life,
   mandatory LSPosed modules and TikTok performance remain unverified.
