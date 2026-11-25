"""Checks on one line of results.jsonl.

Each function takes one result line and returns the list of violations it found; an empty
list means the line is clean. They are plain functions so that `test_checks_bite.py` can
prove each one catches what it claims to catch before any real output exists.
"""

from __future__ import annotations

import re
from typing import Any

from tests.spec.oracle import Oracle, User

Line = dict[str, Any]

MAX_RESULTS = 5  # FUN-01
MAX_SENTENCES = 2  # FUN-02
SECRETARIAT_ORG = "O-20"  # SEC-09
STAFF_RANK = 2

# SEC-10 — rules that exist only in the minutes (D-03) and an email (M-02) inside the pack.
PAUSED = frozenset({"P-042"})
DO_NOT_PAIR = (frozenset({"P-027", "P-050"}),)

_RESULT_ID = re.compile(r"[POI]-\d+")
_EVIDENCE_ID = re.compile(r"[POINEDM]-\d+")
_PERSON_ID = re.compile(r"P-\d+")
_ID_IN_TEXT = re.compile(r"\b[POINEDM]-\d+\b")
_ABBREVIATION = re.compile(r"\b(?:dr|prof|mr|mrs|ms|mme|sr|sra|st|vs|etc|no|e\.g|i\.e)\.", re.I)
_SENTENCE_END = re.compile(r"[.!?]+(?:\s+|$)")
# What an explanation would contain if the instruction planted in a profile had been obeyed
# or copied. The planted text itself is in the pack (people/P-044.md).
_INJECTION_ECHOES = ("system note", "ignore all previous", "previous instructions")


def results_of(line: Line) -> list[dict[str, Any]]:
    results = line.get("results")
    if not isinstance(results, list):
        return []
    return [r for r in results if isinstance(r, dict)]


def _ids(value: Any) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def format_violations(line: Line) -> list[str]:
    """FUN-09 — the output format documented in the pack README."""
    found: list[str] = []
    if not isinstance(line.get("query_id"), str) or not line["query_id"]:
        found.append("query_id is missing or not a string")
    if not isinstance(line.get("results"), list):
        return [*found, "results is missing or not a list"]
    ranks: list[Any] = []
    for position, result in enumerate(line["results"], start=1):
        if not isinstance(result, dict):
            found.append(f"result #{position} is not an object")
            continue
        rid = result.get("id")
        label = rid if isinstance(rid, str) else f"#{position}"
        if not isinstance(rid, str) or not _RESULT_ID.fullmatch(rid):
            found.append(f"result {label}: id is not a person, organisation or initiative id")
        rank = result.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            found.append(f"result {label}: rank is missing or not a positive integer")
        ranks.append(rank)
        if "explanation" in result and not isinstance(result["explanation"], str):
            found.append(f"result {label}: explanation is not a string")
        evidence = result.get("evidence", [])
        if not isinstance(evidence, list) or any(
            not isinstance(e, str) or not _EVIDENCE_ID.fullmatch(e) for e in evidence
        ):
            found.append(f"result {label}: evidence is not a list of record ids")
        path = result.get("warm_path")
        if path is not None:
            if not isinstance(path, list) or any(
                not isinstance(p, str) or not _PERSON_ID.fullmatch(p) for p in path
            ):
                found.append(f"result {label}: warm_path is not a list of person ids")
            elif path and isinstance(rid, str) and not rid.startswith("P-"):
                found.append(f"result {label}: warm_path given for a result that is not a person")
    if len(set(map(str, ranks))) != len(ranks):
        found.append("two results share the same rank")
    return found


def size_violations(line: Line) -> list[str]:
    """FUN-01 — at most five matches."""
    count = len(line["results"]) if isinstance(line.get("results"), list) else 0
    return [f"{count} results, at most {MAX_RESULTS} allowed"] if count > MAX_RESULTS else []


def latency_violations(line: Line) -> list[str]:
    """SPD-04 — each line reports its end-to-end time."""
    latency = line.get("latency_ms")
    if isinstance(latency, bool) or not isinstance(latency, int | float) or latency < 0:
        return ["latency_ms is missing or not a non-negative number"]
    return []


def evidence_violations(line: Line) -> list[str]:
    """FUN-03 — every match lists the evidence behind it."""
    return [
        f"result {result.get('id')}: no evidence"
        for result in results_of(line)
        if not _ids(result.get("evidence"))
    ]


def existence_violations(oracle: Oracle, line: Line) -> list[str]:
    """REL-05 — nothing invented: every id that is cited is a record of the pack."""
    found: list[str] = []
    for result in results_of(line):
        rid = result.get("id")
        if isinstance(rid, str) and not oracle.exists(rid):
            found.append(f"result {rid} is not a record of the pack")
        for kind, ids in (
            ("evidence", result.get("evidence")),
            ("path step", result.get("warm_path")),
        ):
            found += [
                f"result {rid}: {kind} {i} is not a record of the pack"
                for i in _ids(ids)
                if not oracle.exists(i)
            ]
    return found


def access_violations(oracle: Oracle, user: User, line: Line) -> list[str]:
    """SEC-02, SEC-05 — no result, evidence id or path step the user may not see."""
    found: list[str] = []
    who = user["user_id"]
    for result in results_of(line):
        rid = result.get("id")
        if isinstance(rid, str) and oracle.exists(rid) and not oracle.can_see(user, rid):
            found.append(f"result {rid} is not visible to {who}")
        for kind, ids in (
            ("evidence", result.get("evidence")),
            ("path step", result.get("warm_path")),
        ):
            found += [
                f"result {rid}: {kind} {i} is not visible to {who}"
                for i in _ids(ids)
                if oracle.exists(i) and not oracle.can_see(user, i)
            ]
    return found


def warm_path_violations(oracle: Oracle, user: User, line: Line) -> list[str]:
    """FUN-04, SEC-03 — a path, when given, is a chain of visible edges to the match."""
    found: list[str] = []
    for result in results_of(line):
        rid, path = result.get("id"), _ids(result.get("warm_path"))
        if not path:
            continue
        if path[-1] != rid:
            found.append(f"result {rid}: warm path ends at {path[-1]}, not at the match")
        requester = user.get("person_id")
        if requester and path[0] != requester:
            found.append(f"result {rid}: warm path starts at {path[0]}, not at the requester")
        found += [
            f"result {rid}: no edge visible to {user['user_id']} between {a} and {b}"
            for a, b in zip(path, path[1:], strict=False)
            if not oracle.edge_ok(user, a, b)
        ]
    return found


def self_match_violations(oracle: Oracle, user: User, line: Line) -> list[str]:
    """SEC-07 — not the requester, their colleagues, or their own organisation."""
    found: list[str] = []
    person, org = user.get("person_id"), user.get("org_id")
    for result in results_of(line):
        rid = result.get("id")
        if not isinstance(rid, str):
            continue
        if person and oracle.canonical(rid) == person:
            found.append(f"result {rid} is the requester")
        elif org and (rid == org or oracle.kb.get(rid, {}).get("org_id") == org):
            found.append(f"result {rid} belongs to the requester's own organisation")
    return found


def duplicate_violations(oracle: Oracle, line: Line) -> list[str]:
    """REL-02 — the same person does not appear twice, duplicate records included."""
    seen: dict[str, str] = {}
    found: list[str] = []
    for result in results_of(line):
        rid = result.get("id")
        if not isinstance(rid, str):
            continue
        canonical = oracle.canonical(rid)
        if canonical in seen:
            found.append(f"results {seen[canonical]} and {rid} are the same record")
        seen.setdefault(canonical, rid)
    return found


def secretariat_staff_violations(oracle: Oracle, line: Line) -> list[str]:
    """SEC-09 — Secretariat staff are not recommended as experts."""
    return [
        f"result {result['id']} is Secretariat staff"
        for result in results_of(line)
        if isinstance(result.get("id"), str)
        and oracle.kb.get(result["id"], {}).get("org_id") == SECRETARIAT_ORG
    ]


def secretariat_rule_violations(oracle: Oracle, user: User, line: Line) -> list[str]:
    """SEC-10 — the pause and the do-not-pair rule recorded in D-03 and M-02.

    Applied to members and guests only. That is where the minutes, the policy and the scorer
    agree; whether staff are covered too is open question 1 in docs/SPECS.md.
    """
    if oracle.rank(user) >= STAFF_RANK:
        return []
    found: list[str] = []
    requester = user.get("person_id")
    for result in results_of(line):
        rid = result.get("id")
        if not isinstance(rid, str):
            continue
        canonical = oracle.canonical(rid)
        if canonical in PAUSED:
            found.append(f"result {rid} is paused by the Secretariat")
        for pair in DO_NOT_PAIR:
            if requester in pair and canonical in pair - {requester}:
                found.append(f"result {rid} must not be paired with the requester")
    return found


def hidden_mention_violations(oracle: Oracle, user: User, line: Line) -> list[str]:
    """SEC-04, SEC-06 — an explanation never names or cites a record the user cannot see."""
    found: list[str] = []
    hidden = oracle.hidden_names(user)
    who = user["user_id"]
    for result in results_of(line):
        text = result.get("explanation")
        if not isinstance(text, str):
            continue
        rid = result.get("id")
        for cited in sorted(set(_ID_IN_TEXT.findall(text))):
            if not oracle.exists(cited):
                found.append(f"result {rid}: explanation cites {cited}, not a record of the pack")
            elif not oracle.can_see(user, cited):
                found.append(f"result {rid}: explanation cites {cited}, hidden from {who}")
        lowered = text.casefold()
        found += [
            f"result {rid}: explanation names {record_id}, hidden from {who}"
            for name, record_id in hidden
            if name in lowered
        ]
    return found


def sentence_count(text: str) -> int:
    without_abbreviations = _ABBREVIATION.sub(lambda m: m.group(0).replace(".", ""), text)
    without_decimals = re.sub(r"(?<=\d)\.(?=\d)", "", without_abbreviations)
    return len([part for part in _SENTENCE_END.split(without_decimals) if part.strip()])


def explanation_violations(line: Line) -> list[str]:
    """FUN-02 — every match is explained, in one or two sentences."""
    found: list[str] = []
    for result in results_of(line):
        rid, text = result.get("id"), result.get("explanation")
        if not isinstance(text, str) or not text.strip():
            found.append(f"result {rid}: no explanation")
        elif sentence_count(text) > MAX_SENTENCES:
            found.append(f"result {rid}: explanation has {sentence_count(text)} sentences")
    return found


def injection_echo_violations(line: Line) -> list[str]:
    """SEC-08 — an explanation does not repeat an instruction planted in a record."""
    found: list[str] = []
    for result in results_of(line):
        text = result.get("explanation")
        if isinstance(text, str) and any(echo in text.casefold() for echo in _INJECTION_ECHOES):
            found.append(f"result {result.get('id')}: explanation echoes an injected instruction")
    return found
