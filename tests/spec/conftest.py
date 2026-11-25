"""Fixtures for the spec tests: the oracle, and the results file when there is one."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.spec import report
from tests.spec.oracle import (
    SECRETARIAT_RULES_FILE,
    Oracle,
    Scorecard,
    load_oracle,
    read_jsonl,
    run_scorer,
)
from tests.spec.registry import REPO_ROOT

PACK_DIR = REPO_ROOT / "data" / "meridian_case_pack"

# Where the system's output is expected, and how to point the tests at another file or at
# another set of requests (the hidden ones, for instance).
RESULTS_ENV = "MERIDIAN_RESULTS"
QUERIES_ENV = "MERIDIAN_QUERIES"
DEFAULT_RESULTS = Path("results") / "results.jsonl"


def _from_repo(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


@pytest.fixture(scope="session")
def oracle() -> Oracle:
    queries = os.environ.get(QUERIES_ENV)
    return load_oracle(PACK_DIR, _from_repo(queries) if queries else None)


@pytest.fixture(scope="session")
def results_path() -> Path:
    path = _from_repo(os.environ.get(RESULTS_ENV, str(DEFAULT_RESULTS)))
    if not path.is_file():
        pytest.skip(f"no results file yet ({os.environ.get(RESULTS_ENV, DEFAULT_RESULTS)})")
    return path


@pytest.fixture(scope="session")
def results(results_path: Path) -> list[dict[str, Any]]:
    return read_jsonl(results_path)


@pytest.fixture(scope="session")
def scorecard(oracle: Oracle, results_path: Path, request: pytest.FixtureRequest) -> Scorecard:
    card = run_scorer(oracle, results_path, rules=SECRETARIAT_RULES_FILE)
    request.config.stash[report.SCORER_OUTPUT] = card.raw
    return card
