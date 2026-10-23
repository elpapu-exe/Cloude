# Dependency source notes for ChatGPT Kernel

Status: dependency provenance review. This document does not establish a reproducible R10 binary, device boot compatibility, or a performance improvement. Machine-readable file URLs, sizes, and SHA-256 values are recorded in [dependency-pins.json](dependency-pins.json). The project source lock is maintained separately; this review does not change it.

## ReSukiSU: exact source commit identified

The reported R10 component version `v4.2.0-rc1-7e92d45e` resolves to commit [`7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea`](https://github.com/Baka-SU/BakaSU/commit/7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea), committed on 14 September 2026 at 11:24:02 UTC. The historical `ReSukiSU/ReSukiSU` repository redirects to `Baka-SU/BakaSU`; the files at this historical commit still identify the component as ReSukiSU. A repository rename does not authorize updating to its current branch.

The tag `v4.2.0-rc1` currently resolves to `a9216b04e29cc973ddbf845342f2cbf85b47b460`, a different commit. Pin the full R10 component commit rather than substituting the tag. The immutable [setup script](https://github.com/Baka-SU/BakaSU/blob/7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea/kernel/setup.sh) is a reference for integration, not a script executed by this audit. Its default branch selection and pull behavior must not silently select newer code.

### Preserve Git-derived version metadata

The pinned [kernel/Kbuild](https://github.com/Baka-SU/BakaSU/blob/7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea/kernel/Kbuild) contains these relevant rules:

- `REPO_NAME := ReSukiSU` is fixed in the source.
- `KSU_VERSION` is `30000 + git rev-list --count HEAD + 700`.
- `KSU_TAG_NAME` comes from `git describe --abbrev=0 --tags`, falling back to `v4.1.0` if no tag is available.
- The commit portion comes from `git rev-parse --short=8 HEAD`, with a dirty suffix if the repository differs from HEAD.
- `CONFIG_KSU_FULL_NAME_FORMAT` controls how tag, commit, repository, branch, and numeric code are combined.

Kbuild checks that Git metadata exists next to its `kernel` directory. It also attempts `git fetch --unshallow` when a shallow repository is detected. Therefore a source tarball copied into a directory is not equivalent to a complete Git checkout for version generation. A shallow checkout can also produce a different numeric version if its history is counted before being completed.

The preferred method is to prepare complete reachable Git history and relevant tags explicitly, check out the full pinned commit, then record the following read-only results before the build. Do not allow an unreviewed `main`, `latest`, or implicit network fetch to choose the dependency during compilation.

```sh
git -C "$KSU_REPOSITORY" rev-parse HEAD
git -C "$KSU_REPOSITORY" rev-parse --is-shallow-repository
git -C "$KSU_REPOSITORY" rev-list --count HEAD
git -C "$KSU_REPOSITORY" describe --abbrev=0 --tags
git -C "$KSU_REPOSITORY" describe --tags --always
git -C "$KSU_REPOSITORY" status --porcelain
```

The checkout must report the full pin above, `false` for shallow history, the intended nearest tag, and only documented changes. Preserve the measured reachable count and its formula in build metadata. If an offline export is required later, any replacement of automatic Git-derived metadata must be an explicit audited build-system patch using that verified count, tag, and SHA. Do not invent a count, use a shallow count, or silently spoof a release identity.

The fixed GitHub tree page reports a commit count of `4,442` in its page data. This audit did not independently validate that display value with `git rev-list --count`; it is not the recorded authoritative build counter, and no numeric KSU version is asserted here.

## SUSFS: fixed chronological candidate, not exact R10 provenance

The reviewed kernel source is [R10 commit `d246c8c17548bb1a2756092cabf34d11eedcde8c`](https://github.com/belowzeroiq/kernel_msm-5.15/tree/d246c8c17548bb1a2756092cabf34d11eedcde8c). It lacks `fs/susfs.c` and `include/linux/susfs.h`; the sampled `fs/open.c` and `fs/Makefile` lack SUSFS integration. Consequently those additions were not represented by that kernel commit alone. Their presence in the released kernel depended on later build-time integration.

The SUSFS branch history returned [`7af04b08f86a5f811cbea28805f96d52368e005f`](https://gitlab.com/simonpunk/susfs4ksu/-/commit/7af04b08f86a5f811cbea28805f96d52368e005f) as the latest commit before 14 September 2026 at 12:00 UTC. That commit is dated 13 September 2026 at 07:09:55 UTC and its [header](https://gitlab.com/simonpunk/susfs4ksu/-/raw/7af04b08f86a5f811cbea28805f96d52368e005f/kernel_patches/include/linux/susfs.h) declares `SUSFS_VERSION "v2.3.0"`.

This makes it a source-controlled candidate for reconstructing the historical recipe. It does not prove R10 used this exact commit: no original build manifest or binary/source attestation was located, and multiple commits may share `v2.3.0`. Describe it as a chronological candidate until that gap is resolved. Do not replace it silently with the current branch tip, which has changed since the release.

### Reviewed source inputs

Use the immutable raw URLs and calculated hashes in the JSON companion for these files:

- `kernel_patches/50_add_susfs_in_gki-android13-5.15.patch`
- `kernel_patches/fs/susfs.c`
- `kernel_patches/include/linux/susfs.h`
- `kernel_patches/include/linux/susfs_def.h`
- `README.md`, for the integration instructions at the same candidate commit

Hashes were computed locally from HTTPS responses with normal TLS verification. They identify the reviewed bytes; they are not publisher signatures or independently published official archive checksums. Neither the ReSukiSU archive nor the SUSFS archive was downloaded or hashed by this audit.

### Integration constraints

The pinned ReSukiSU source already contains `CONFIG_KSU_SUSFS`, its SUSFS feature configuration, compatibility logic, and inline hook checks. Its Kbuild rejects an enabled SUSFS configuration if required kernel-side files are absent. The generic `kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch` targets upstream KernelSU; it is not automatically applicable to ReSukiSU and must not be applied blindly.

The kernel-side 5.15 patch and source/header files still require an explicit patch audit against the fixed R10 source. No patch application or compile was performed during this dependency review. Reject unresolved hunks and inspect the resulting hooks rather than treating a failed patch followed by file copying as a complete integration. Preserve the existing KSU manager interface and intended root behavior when comparing a baseline rebuild.

## Remaining evidence needed

1. Validate Git-derived KSU count, tag, version format, and resulting numeric code from complete local history.
2. Establish exact SUSFS release provenance, or retain the chronological-candidate qualification in artifacts and release notes.
3. Validate kernel patch application and generated configuration against the working R10 baseline.
4. Complete toolchain and configuration provenance before any claim of an equivalent or optimized build.

This review changes only the two dependency documents; it does not update a source lock, kernel checkout, build configuration, or phone.
