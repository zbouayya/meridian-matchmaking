"""Locate the case data pack and prove it is byte-identical to what was received.

Nothing here interprets the pack's content. The pack ships the evaluation labels and the
scorer next to the data, so a silently edited file — a line-ending conversion on checkout is
enough — would change the scores without changing a line of our code. The manifest
(`data/meridian_case_pack.sha256`) was generated once from the original zip and is the
reference; `sha256sum -c` reads the same file.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

PACK_ENV = "MERIDIAN_PACK_DIR"
DEFAULT_PACK_DIR = Path("data") / "meridian_case_pack"


class PackNotFoundError(Exception):
    """The pack directory or its manifest is not where it was expected."""


@dataclass(frozen=True)
class PackCheck:
    pack_dir: Path
    expected: int
    missing: tuple[str, ...]
    modified: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.missing or self.modified or self.unexpected)


def resolve_pack_dir(explicit: Path | None = None) -> Path:
    """An explicit path wins, then $MERIDIAN_PACK_DIR, then ./data/meridian_case_pack."""
    if explicit is not None:
        return explicit
    from_env = os.environ.get(PACK_ENV)
    return Path(from_env) if from_env else DEFAULT_PACK_DIR


def manifest_path(pack_dir: Path) -> Path:
    """The manifest sits beside the pack, never inside it: the pack stays as received."""
    return pack_dir.with_name(pack_dir.name + ".sha256")


def read_manifest(path: Path) -> dict[str, str]:
    """Parse `sha256sum` output: `<hex digest>  <relative path>` per line."""
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            entries[name.lstrip("*")] = digest
    return entries


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_bytecode(path: Path) -> bool:
    # Running the pack's scorer can leave bytecode behind; that is not a change to the pack.
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def check_pack(pack_dir: Path) -> PackCheck:
    manifest = manifest_path(pack_dir)
    if not pack_dir.is_dir():
        raise PackNotFoundError(f"data pack not found: {pack_dir}")
    if not manifest.is_file():
        raise PackNotFoundError(f"manifest not found: {manifest}")

    expected = read_manifest(manifest)
    actual = {
        p.relative_to(pack_dir).as_posix(): _digest(p)
        for p in pack_dir.rglob("*")
        if p.is_file() and not _is_bytecode(p)
    }
    return PackCheck(
        pack_dir=pack_dir,
        expected=len(expected),
        missing=tuple(sorted(expected.keys() - actual.keys())),
        modified=tuple(
            sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
        ),
        unexpected=tuple(sorted(actual.keys() - expected.keys())),
    )
