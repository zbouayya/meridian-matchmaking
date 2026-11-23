"""The pack integrity check: it must pass on the committed pack and fail on any change."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from matchmaker.pack import (
    PACK_ENV,
    PackNotFoundError,
    check_pack,
    manifest_path,
    resolve_pack_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED_PACK = REPO_ROOT / "data" / "meridian_case_pack"


def _make_pack(root: Path, files: dict[str, bytes]) -> Path:
    pack = root / "pack"
    lines = []
    for name, content in files.items():
        target = pack / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        lines.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
    manifest_path(pack).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return pack


def test_committed_pack_is_the_one_that_was_received() -> None:
    result = check_pack(COMMITTED_PACK)
    assert result.ok, (result.missing, result.modified, result.unexpected)
    assert result.expected == 86


def test_intact_pack_passes(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path, {"a.md": b"one\n", "sub/b.csv": b"x,y\r\n1,2\r\n"})
    assert check_pack(pack).ok


def test_a_line_ending_conversion_is_caught(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path, {"sub/b.csv": b"x,y\r\n1,2\r\n"})
    (pack / "sub" / "b.csv").write_bytes(b"x,y\n1,2\n")
    result = check_pack(pack)
    assert not result.ok
    assert result.modified == ("sub/b.csv",)


def test_missing_and_unexpected_files_are_reported(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path, {"a.md": b"one\n", "b.md": b"two\n"})
    (pack / "b.md").unlink()
    (pack / "c.md").write_bytes(b"three\n")
    result = check_pack(pack)
    assert result.missing == ("b.md",)
    assert result.unexpected == ("c.md",)


def test_bytecode_left_by_the_scorer_is_not_a_change(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path, {"eval/score.py": b"print('x')\n"})
    cache = pack / "eval" / "__pycache__"
    cache.mkdir()
    (cache / "score.cpython-312.pyc").write_bytes(b"\x00")
    assert check_pack(pack).ok


def test_a_missing_pack_or_manifest_is_an_error_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises(PackNotFoundError):
        check_pack(tmp_path / "nowhere")
    (tmp_path / "bare").mkdir()
    with pytest.raises(PackNotFoundError):
        check_pack(tmp_path / "bare")


def test_pack_dir_resolution_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PACK_ENV, raising=False)
    assert resolve_pack_dir() == Path("data") / "meridian_case_pack"
    monkeypatch.setenv(PACK_ENV, str(tmp_path / "from-env"))
    assert resolve_pack_dir() == tmp_path / "from-env"
    assert resolve_pack_dir(tmp_path / "explicit") == tmp_path / "explicit"
