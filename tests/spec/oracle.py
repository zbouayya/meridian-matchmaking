"""The scorer that came with the case, loaded as the oracle.

The access rules are deliberately not re-implemented: what a user may see, which records are
duplicates and how a document is classified all come from `eval/score.py` inside the pack.
A spec test and the scorer run at the debrief therefore cannot disagree on what a leak is.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

Record = dict[str, Any]
User = dict[str, Any]

# The scorer's undocumented `--rules` input, written from the minutes (D-03) and email (M-02).
SECRETARIAT_RULES_FILE = Path(__file__).with_name("secretariat_rules.json")

_TITLES = re.compile(r"^(?:dr|prof|mr|mrs|ms|mme|sr|sra)\.?\s+", re.IGNORECASE)
_MIN_NAME_LENGTH = 6


def load_scorer(pack: Path) -> ModuleType:
    path = pack / "eval" / "score.py"
    spec = importlib.util.spec_from_file_location("meridian_scorer", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the scorer at {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # the pack is stored as received: no __pycache__ in it
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@dataclass(frozen=True)
class Oracle:
    pack: Path
    scorer: ModuleType
    kb: dict[str, Record]
    edges: dict[frozenset[str], list[dict[str, str]]]
    users: dict[str, User]
    queries: dict[str, dict[str, Any]]
    queries_path: Path

    def rank(self, user: User) -> int:
        """Clearance as a number: public 0, members 1, staff 2, restricted 3."""
        return int(self.scorer.VIS[user["clearance"]])

    def exists(self, record_id: str) -> bool:
        return record_id in self.kb

    def can_see(self, user: User, record_id: str) -> bool:
        return bool(self.scorer.can_see(self.kb, user, record_id))

    def edge_ok(self, user: User, a: str, b: str) -> bool:
        return bool(self.scorer.edge_ok(self.kb, self.edges, user, a, b))

    def canonical(self, record_id: str) -> str:
        return str(self.scorer.ALIASES.get(record_id, record_id))

    def user_for(self, query_id: str) -> User | None:
        query = self.queries.get(query_id)
        return None if query is None else self.users[query["user_id"]]

    def hidden_names(self, user: User) -> list[tuple[str, str]]:
        """(name, id) of every named record this user cannot see.

        A name that is also part of a visible record's name is left out: mentioning it does
        not prove that the hidden record was referred to.
        """
        visible: list[str] = []
        hidden: list[tuple[str, str]] = []
        for record_id, record in self.kb.items():
            label = record.get("name") or record.get("title")
            if not isinstance(label, str):
                continue
            variants = {label.casefold(), _TITLES.sub("", label).casefold()}
            if self.can_see(user, record_id):
                visible.extend(variants)
            else:
                hidden.extend((v, record_id) for v in variants if len(v) >= _MIN_NAME_LENGTH)
        return sorted({(n, i) for n, i in hidden if not any(n in v for v in visible)})


def load_oracle(pack: Path, queries_path: Path | None = None) -> Oracle:
    scorer = load_scorer(pack)
    kb, edges, users = scorer.load_pack(str(pack))
    queries_file = queries_path or pack / "eval" / "queries_public.jsonl"
    queries = {q["query_id"]: q for q in read_jsonl(queries_file)}
    return Oracle(pack, scorer, kb, edges, users, queries, queries_file)


@dataclass(frozen=True)
class Scorecard:
    """What `eval/score.py` printed, parsed. `raw` is the output itself."""

    raw: str
    ndcg: float
    precision: float
    access_violations: int
    self_org: int
    duplicates: int
    injection_signals: int
    warm_paths: tuple[int, int] | None
    evidence: tuple[int, int] | None
    latency_p95_ms: int | None
    rule_breaks: int | None
    missing: int
    gate_passed: bool


def _number(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def _required(pattern: str, text: str) -> str:
    value = _number(pattern, text)
    if value is None:
        raise ValueError(f"the scorer output has no line matching {pattern!r}:\n{text}")
    return value


def _fraction(pattern: str, text: str) -> tuple[int, int] | None:
    match = re.search(pattern, text, re.MULTILINE)
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_scorer_output(text: str) -> Scorecard:
    p95 = _number(r"^latency p50 / p95\s+\d+ ms / (\d+) ms", text)
    breaks = _number(r"^business-rule breaks (\d+)", text)
    return Scorecard(
        raw=text,
        ndcg=float(_required(r"^mean nDCG@5\s+([\d.]+)", text)),
        precision=float(_required(r"^mean P@5\s+([\d.]+)", text)),
        access_violations=int(_required(r"^access violations\s+(\d+)", text)),
        self_org=int(_required(r"^self/own-org recs\s+(\d+)", text)),
        duplicates=int(_required(r"^duplicates\s+(\d+)", text)),
        injection_signals=int(_required(r"^injection signals\s+(\d+)", text)),
        warm_paths=_fraction(r"^warm paths valid\s+(\d+)/(\d+)", text),
        evidence=_fraction(r"^evidence grounded\s+(\d+)/(\d+)", text),
        latency_p95_ms=None if p95 is None else int(p95),
        rule_breaks=None if breaks is None else int(breaks),
        missing=int(_number(r"^missing queries\s+(\d+)", text) or 0),
        gate_passed=_required(r"^SECURITY GATE: (PASS|FAIL)", text) == "PASS",
    )


def run_scorer(oracle: Oracle, results: Path, rules: Path | None = None) -> Scorecard:
    """Run the scorer exactly as its README says, in process, and parse what it prints.

    `--rules` is an argument the scorer accepts but does not document; it counts breaks of
    the Secretariat introduction rules (SEC-10).
    """
    argv = [
        "score.py",
        "--results",
        str(results),
        "--queries",
        str(oracle.queries_path),
        "--pack",
        str(oracle.pack),
    ]
    if rules is not None:
        argv += ["--rules", str(rules)]
    output = io.StringIO()
    previous = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(output):
            oracle.scorer.main()
    finally:
        sys.argv = previous
    return parse_scorer_output(output.getvalue())
