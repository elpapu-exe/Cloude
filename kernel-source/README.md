# Complete corresponding sources for ChatGPT Kernel 0.1.0-rc1

`linux/` is the exact patched kernel tree used for the distributed Image.
`kernelsu/` is ReSukiSU at 7e92d45ed5c7e0ed6e3e0f7e87d1cea510d068ea.
`baseband-guard/` is revision a54e0dc6cf0aff4dd87fec49644a02d2eb612905.
SUSFS sources and hooks are already included in linux/; their immutable inputs are recorded in config/sources.lock.json at the repository root.

Nested Git metadata is excluded. The unmodified rebuilding scripts at the repository root obtain the pinned upstream histories, apply the distributed patches and use config/effective.config for comparison. See docs/build.md. Licenses and attribution are preserved in each component.

The distributed experimental binary has not been boot-tested on the phone. See downloads/release-notes.md and downloads/LEEME-instalacion.md.
