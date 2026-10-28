# Corresponding source snapshots

`linux/` contains the patched source for the **new reconstruction 0.1.0-rc3-rebuild1**. It is not the exact lost rc3 source or a claim that the new image has compiled. `kernelsu/` is pinned ReSukiSU 7e92d45e, and `baseband-guard/` is a54e0dc6. SUSFS source/hooks are included in Linux, with immutable input hashes and provenance limits in `config/sources.lock.json`.

The historical rc1 binary and metadata remain in `downloads/`; their corresponding sources are preserved by Git commit `4fc1ad554ac54ffce0a6792ca6d85f67435e8a86`. Do not associate them with the current changed source snapshot.

The recipe obtains original pinned histories, applies the patch series and verifies results. Nested Git metadata is excluded from snapshots and release archives. KSU's build identity uses actual complete Git history acquired by the recipe, never synthetic history. Licenses and attribution are preserved. See `docs/build.md` for checks and hardware limitations.
