"""The rule-based baseline, end to end: requests in, one result line per request out.

    request -> who is asking -> records they may be offered -> rule-based ranking -> result line

It exists to be beaten: every later component is measured against this file's output. It
goes through the same access filter as everything else, so the comparison is about ranking
and never about leaks. No model is called.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from matchmaker import access, dedupe, ranking, sanitize, taxonomy
from matchmaker.corpus import KINDS, Corpus, load

MAX_RESULTS = 5
# Said when the request comes from a user id the pack does not know. Nothing is searched:
# without a known user there is no clearance to apply.
UNKNOWN_USER_NOTE = (
    "The requester is not a known user, so nothing was searched. This is a data question "
    "for a relationship manager."
)
# Said in the answer whenever the request does not name the kind of answer it wants.
ALL_KINDS_NOTE = (
    "The request did not say which kind of answer was wanted, so people, organisations "
    "and initiatives were all searched."
)


@dataclass(frozen=True)
class Request:
    """What the tool is given. The evaluation labels sit in the same file and are never read."""

    query_id: str
    user_id: str
    query: str
    entity_types: tuple[str, ...]
    kinds_stated: bool = True  # False when the request did not say which kinds it wants


def read_requests(path: Path) -> list[Request]:
    requests: list[Request] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        kinds = tuple(k for k in raw.get("entity_types") or () if k in KINDS)
        requests.append(
            Request(raw["query_id"], raw["user_id"], raw["query"], kinds or KINDS, bool(kinds))
        )
    return requests


def note_for(request: Request, known_user: bool = True) -> str | None:
    """What the requester must be told about how the request was read, if anything."""
    if not known_user:
        return UNKNOWN_USER_NOTE
    return None if request.kinds_stated else ALL_KINDS_NOTE


def answer(
    corpus: Corpus,
    request: Request,
    *,
    ranker: ranking.Ranker | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """One result line, in the format the pack's README documents."""
    started = time.perf_counter()
    rank = ranker or ranking.make_ranker(ranking.Options())
    results: list[dict[str, Any]] = []
    user = corpus.users.get(request.user_id)
    # An unknown user is offered nothing.
    if user is not None:
        pool = dedupe.merge_duplicates(access.candidates(corpus, user, request.entity_types, today))
        for position, match in enumerate(
            rank(" ".join(sanitize.clean(request.query).split()), pool)[:MAX_RESULTS], start=1
        ):
            explanation = ranking.describe(match)
            flag = access.flag(user, match.record, today)
            results.append(
                {
                    "id": match.record.id,
                    "rank": position,
                    "explanation": f"{explanation} {flag}" if flag else explanation,
                    "evidence": [match.record.id],
                }
            )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    line = {"query_id": request.query_id, "latency_ms": latency_ms, "results": results}
    note = note_for(request, user is not None)
    return line | {"note": note} if note else line


def run(
    pack_dir: Path,
    queries: Path,
    out: Path,
    *,
    options: ranking.Options | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Answer every request in `queries` and write the lines to `out`."""
    corpus = load(pack_dir)
    options = options or ranking.Options()
    themes = taxonomy.load(pack_dir) if options.uses_taxonomy else None
    ranker = ranking.make_ranker(options, themes)
    lines = [
        answer(corpus, request, ranker=ranker, today=today) for request in read_requests(queries)
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as file:
        for line in lines:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
    return lines
