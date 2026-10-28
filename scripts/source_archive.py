#!/usr/bin/env python3
"""Verify source archives and describe trees without manufacturing Git history."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree_manifest(root: Path) -> list[dict]:
    entries = []

    def visit(directory: Path):
        for item in sorted(directory.iterdir()):
            if item.name in ('.git', '__pycache__') or item.name.endswith('.pyc'):
                continue
            relative = item.relative_to(root).as_posix()
            if item.is_symlink():
                entries.append({'path': relative, 'type': 'symlink', 'target': os.readlink(item)})
            elif item.is_dir():
                entries.append({'path': relative, 'type': 'directory'})
                visit(item)
            elif item.is_file():
                entries.append({'path': relative, 'type': 'file', 'sha256': sha256(item),
                                'executable': bool(item.stat().st_mode & 0o111)})
            else:
                raise RuntimeError(f'Unsupported source entry: {relative}')

    visit(root)
    return entries


def tree_digest(root: Path) -> str:
    return hashlib.sha256(json.dumps(tree_manifest(root), sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def archive_root(package: tarfile.TarFile, commit: str) -> str:
    """Validate the entire member list before creating any files."""
    roots = set()
    names = set()
    for member in package.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts or not path.parts:
            raise ValueError(f'Unsafe source archive member: {member.name}')
        if member.name in names:
            raise ValueError(f'Duplicate source archive member: {member.name}')
        names.add(member.name)
        roots.add(path.parts[0])
        if not (member.isfile() or member.isdir() or member.issym()):
            raise ValueError(f'Unsupported source archive member: {member.name}')
        if member.issym():
            target = PurePosixPath(member.linkname)
            if target.is_absolute():
                raise ValueError(f'Absolute source symlink: {member.name}')
            depth = len(path.parts) - 1
            for part in target.parts:
                if part == '..':
                    depth -= 1
                elif part != '.':
                    depth += 1
                if depth < 1:
                    raise ValueError(f'Escaping source symlink: {member.name}')
    if len(roots) != 1 or not next(iter(roots)).endswith('-' + commit):
        raise ValueError('Source archive must have one root named for its complete pinned commit')
    return next(iter(roots))


def extract_source(archive: Path, destination: Path, commit: str, expected_sha256: str) -> None:
    if sha256(archive) != expected_sha256:
        raise ValueError('Source archive SHA256 mismatch')
    if destination.exists():
        raise FileExistsError(f'Refusing to replace existing source: {destination}')
    # The caller supplies a private staging directory. tarfile's data filter
    # independently rejects traversal through links and unsafe special entries.
    with tarfile.open(archive) as package:
        prefix = archive_root(package, commit)
        stage = destination.parent / (destination.name + '-extract')
        stage.mkdir()
        try:
            package.extractall(stage, filter='data')
            (stage / prefix).rename(destination)
        finally:
            import shutil
            shutil.rmtree(stage)


def write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(receipt, indent=2) + '\n')
    temporary.replace(path)
