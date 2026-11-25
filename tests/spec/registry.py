"""docs/SPECS.md is the single source of truth for spec ids; this module reads it.

A spec is a table row whose first cell is an id such as `SEC-02`. The last cell says how it
is enforced. Tests declare what they enforce with `@pytest.mark.spec("SEC-02", ...)`, and
`marked_spec_ids` finds those declarations by parsing the test files, so the bookkeeping
does not depend on which tests happen to be selected in a run.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_FILE = REPO_ROOT / "docs" / "SPECS.md"
TESTS_DIR = REPO_ROOT / "tests"

# test: runs now · results: runs once results.jsonl exists · pending: component not built
# manual: judged by a person
MODES = ("test", "results", "pending", "manual")
ENFORCED_MODES = ("test", "results")

SPEC_ID = re.compile(r"[A-Z]{3}-\d{2}")
_ROW = re.compile(r"^\|\s*(?P<id>[A-Z]{3}-\d{2})\s*\|(?P<rest>.+)\|\s*$")


@dataclass(frozen=True)
class Spec:
    id: str
    requirement: str
    source: str
    mode: str
    partial: bool


def load_specs(path: Path = SPECS_FILE) -> list[Spec]:
    specs: list[Spec] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = _ROW.match(line)
        if match is None:
            continue
        cells = [cell.strip() for cell in match["rest"].split("|")]
        if len(cells) != 3:
            raise ValueError(f"{path.name}:{number}: expected 4 cells in the row of {match['id']}")
        requirement, source, enforced = cells
        specs.append(
            Spec(
                id=match["id"],
                requirement=requirement,
                source=source,
                mode=enforced.split()[0] if enforced else "",
                partial="(partial)" in enforced,
            )
        )
    return specs


def marked_spec_ids(tests_dir: Path = TESTS_DIR) -> dict[str, list[str]]:
    """Spec id -> the tests that declare it, read from the decorators in the test files."""
    found: dict[str, list[str]] = {}
    for path in sorted(tests_dir.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            for decorator in node.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "spec"
                ):
                    continue
                for arg in decorator.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        where = f"{path.relative_to(tests_dir.parent).as_posix()}::{node.name}"
                        found.setdefault(arg.value, []).append(where)
    return found
