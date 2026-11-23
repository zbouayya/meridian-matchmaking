"""The command line: exit codes are the contract CI and the container rely on."""

from __future__ import annotations

from pathlib import Path

import pytest

from matchmaker import __version__
from matchmaker.cli import EXIT_OK, EXIT_PACK_ALTERED, EXIT_PACK_NOT_FOUND, main
from matchmaker.pack import manifest_path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED_PACK = REPO_ROOT / "data" / "meridian_case_pack"


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_check_pack_passes_on_the_committed_pack(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check-pack", "--pack", str(COMMITTED_PACK)]) == EXIT_OK
    assert "OK" in capsys.readouterr().out


def test_check_pack_fails_on_an_altered_pack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "a.md").write_bytes(b"changed\n")
    manifest_path(pack).write_text(f"{'0' * 64}  a.md\n", encoding="utf-8")
    assert main(["check-pack", "--pack", str(pack)]) == EXIT_PACK_ALTERED
    assert "a.md" in capsys.readouterr().err


def test_check_pack_reports_a_missing_pack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check-pack", "--pack", str(tmp_path / "nowhere")]) == EXIT_PACK_NOT_FOUND
    assert "not found" in capsys.readouterr().err


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2
