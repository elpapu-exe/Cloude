#!/usr/bin/env python3
"""Download verified Debian build tools into a local prefix; no system install."""
from __future__ import annotations

import hashlib
import json
import lzma
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
PACKAGES = (
    "bc", "bison", "flex", "m4", "libelf-dev", "libfl2", "libfl-dev",
    "lz4", "pahole", "libdw1t64", "libdw-dev", "libelf1t64", "libbpf-dev", "busybox-static", "cpio",
)


def download(url: str, destination: Path, expected: str | None = None) -> str:
    if destination.exists():
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if expected is None or digest == expected:
            return digest
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as target:
        while data := response.read(1024 * 1024):
            target.write(data)
            digest.update(data)
    result = digest.hexdigest()
    if expected is not None and result != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch: {destination.name}")
    temporary.replace(destination)
    return result


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    lock_path = ROOT / "config" / "host-tools.lock.json"
    selected = json.loads(lock_path.read_text())["packages"] if lock_path.exists() else {}
    if set(PACKAGES) - selected.keys():
        index = CACHE / "debian-trixie-amd64-Packages.xz"
        index_url = "https://deb.debian.org/debian/dists/trixie/main/binary-amd64/Packages.xz"
        index_sha = download(index_url, index)
        selected = {}
        with lzma.open(index, "rt") as source:
            record: dict[str, str] = {}
            for line in source:
                if not line.strip():
                    name = record.get("Package")
                    if name in PACKAGES:
                        selected[name] = {
                            "version": record["Version"],
                            "url": "https://deb.debian.org/debian/" + record["Filename"],
                            "sha256": record["SHA256"],
                            "depends": record.get("Depends", ""),
                        }
                    record = {}
                elif not line.startswith(" ") and ": " in line:
                    key, value = line.rstrip("\n").split(": ", 1)
                    record[key] = value
        missing = set(PACKAGES) - selected.keys()
        if missing:
            raise RuntimeError(f"Packages not found: {sorted(missing)}")
        lock_path.write_text(json.dumps({
            "index_url": index_url, "index_sha256": index_sha,
            "packages": selected,
        }, indent=2) + "\n")
    prefix = CACHE / "host"
    prefix.mkdir(exist_ok=True)
    for name, entry in selected.items():
        archive = CACHE / "host-debs" / entry["url"].rsplit("/", 1)[1]
        download(entry["url"], archive, entry["sha256"])
        subprocess.run(["dpkg-deb", "-x", str(archive), str(prefix)], check=True)
        print(f"Verified and extracted {name} {entry['version']}", flush=True)


if __name__ == "__main__":
    main()
