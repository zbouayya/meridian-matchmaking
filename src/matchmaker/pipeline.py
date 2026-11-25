"""The matchmaker, end to end: a fixed pipeline with one model call per request.

    request -> who is asking -> records they may be offered -> ranking
            -> evidence and warm path, looked up in code -> explanations -> result line

Code ranks and code gathers the evidence; the model only writes the explanations, from
facts already filtered for the user who asked. So an instruction planted in a profile can
neither move a rank nor reach a record, and when the model fails the ranked results still
come back, with rule-based explanations.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import anthropic

from matchmaker import (
    access,
    dedupe,
    evidence,
    explain,
    keyword,
    limits,
    ranking,
    sanitize,
    selection,
    tracing,
)
from matchmaker.baseline import Request, note_for, read_requests
from matchmaker.corpus import Corpus, load

MAX_RESULTS = 5
# What one request may spend waiting for models, all calls together: it keeps the whole
# request under the 4-second target.
TOTAL_MODEL_SECONDS = 3.6


@dataclass(frozen=True)
class Answered:
    line: dict[str, Any]  # the result line, in the format the pack's README documents
    stats: dict[str, Any]  # where the time and the tokens of this request went


def _milliseconds(start: float, end: float) -> float:
    return round((end - start) * 1000, 2)


def _rule_based(match: keyword.Match, found: evidence.Evidence, corpus: Corpus) -> str:
    """The explanation written without a model: why it matched, and how to reach them."""
    sentence = ranking.describe(match)
    path = found.warm_path
    if len(path) == 2:
        return f"{sentence} You already have a direct relationship."
    if len(path) > 2:
        through = " then ".join(corpus.records[p].name for p in path[1:-1])
        return f"{sentence} An introduction is possible through {through}."
    return sentence


def answer(
    corpus: Corpus,
    request: Request,
    ranker: ranking.Ranker | None = None,
    client: anthropic.Anthropic | None = None,
    today: date | None = None,
    *,
    model: str | None = None,
    budget_seconds: float = explain.DEFAULT_BUDGET_SECONDS,
    ledger: limits.Ledger | None = None,
    recent_contact_days: int = limits.RECENT_CONTACT_DAYS,
) -> Answered:
    """Answer one request. `client=None` means no model: rule-based explanations.

    `ledger` counts who has already been suggested; without one, repetition is not limited.
    """
    started = time.perf_counter()
    rank = ranker or ranking.make_ranker(ranking.Options())
    # Hidden text is removed from the request before it is searched or shown to a model.
    query = " ".join(sanitize.clean(request.query).split())
    day = today or date.today()
    results: list[dict[str, Any]] = []
    stats: dict[str, Any] = {"query_id": request.query_id, "user_id": request.user_id}
    user = corpus.users.get(request.user_id)
    # An unknown user is offered nothing.
    if user is not None:
        with tracing.step("matchmaker.request") as span:
            span.set_attribute("matchmaker.query_id", request.query_id)
            span.set_attribute("matchmaker.user_id", request.user_id)
            with tracing.step("matchmaker.access_filter"):
                allowed = access.candidates(corpus, user, request.entity_types, day)
                # People the requester was in touch with recently, or who have already
                # been suggested often enough, are removed here, before any ranking.
                limited = limits.apply(corpus, user, allowed, day, ledger, recent_contact_days)
                # The same person is never offered twice (duplicate records are merged).
                pool = dedupe.merge_duplicates(limited.kept)
            filtered = time.perf_counter()
            hidden = evidence.hidden_names(corpus, user)
            if isinstance(rank, selection.ModelRanker):
                rank.forbidden = hidden
            with tracing.step("matchmaker.rank", "RETRIEVER"):
                matches = rank(query, pool)[:MAX_RESULTS]
            if ledger is not None:
                ledger.record(m.record for m in matches)
            # A ranker that asks a model says so, and what it cost.
            retrieval = dict(getattr(rank, "last", None) or {"by": "rules"})
            ranked = time.perf_counter()
            with tracing.step("matchmaker.evidence", "TOOL"):
                found = [evidence.gather(corpus, user, m.record, day, hidden) for m in matches]
            gathered = time.perf_counter()
            items = [
                explain.Item(m.record.id, e.facts, _rule_based(m, e, corpus), e.ids)
                for m, e in zip(matches, found, strict=True)
            ]
            explained = explain.explain(
                client,
                query,
                items,
                model=model,
                # Whatever the selection step used is taken off the explanation's time.
                budget_seconds=min(
                    budget_seconds,
                    max(TOTAL_MODEL_SECONDS - (time.perf_counter() - started), 0.0),
                ),
                forbidden=hidden,
            )
            written = time.perf_counter()
            for position, (match, proof) in enumerate(zip(matches, found, strict=True), 1):
                text = explained.explanations[match.record.id]
                flag = access.flag(user, match.record, day)
                if flag:
                    # Two sentences at most: the flag takes the place of the second one.
                    text = f"{explain.first_sentence(text)} {flag}"
                result: dict[str, Any] = {
                    "id": match.record.id,
                    "rank": position,
                    "explanation": text,
                    "evidence": list(proof.ids),
                }
                if proof.warm_path:
                    result["warm_path"] = list(proof.warm_path)
                results.append(result)
            span.set_attribute("matchmaker.results", len(results))
        stats |= {
            "candidates": len(pool),
            "left_out": {
                "recent_contact": list(limited.recent_contact),
                "repetition": list(limited.repetition),
            },
            "retrieval": retrieval,
            "results": len(results),
            "ms": {
                "access_filter": _milliseconds(started, filtered),
                "rank": _milliseconds(filtered, ranked),
                "evidence": _milliseconds(ranked, gathered),
                "explain": _milliseconds(gathered, written),
            },
            "model": explained.model,
            "prompt_version": explained.prompt_version,
            "attempts": explained.attempts,
            "input_tokens": explained.input_tokens,
            "output_tokens": explained.output_tokens,
            "cost_usd": explained.cost_usd,
            "explained_by_model": len(explained.written_by_model),
            "fallback": len(explained.written_by_model) < len(items),
            "fallback_reason": explained.fallback_reason,
        }
    latency_ms = _milliseconds(started, time.perf_counter())
    stats["latency_ms"] = latency_ms
    line = {"query_id": request.query_id, "latency_ms": latency_ms, "results": results}
    note = note_for(request, user is not None)
    if note:
        line["note"] = note
    return Answered(line, stats)


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(
    pack_dir: Path,
    queries: Path,
    out: Path,
    *,
    ranker: ranking.Ranker | None = None,
    client: anthropic.Anthropic | None = None,
    today: date | None = None,
    stats_out: Path | None = None,
    model: str | None = None,
    budget_seconds: float = explain.DEFAULT_BUDGET_SECONDS,
    max_suggestions: int = limits.MAX_SUGGESTIONS,
    recent_contact_days: int = limits.RECENT_CONTACT_DAYS,
) -> list[Answered]:
    """Answer every request in `queries`; write the result lines to `out`, one per request.

    `stats_out`, when given, receives one line per request saying where its time and its
    tokens went. One ledger of suggestions is kept for the run, so the requests are
    answered in the order of the file and a person is suggested `max_suggestions` times at
    most.
    """
    corpus = load(pack_dir)
    ledger = limits.Ledger(max_suggestions)
    answers = [
        answer(
            corpus,
            request,
            ranker,
            client,
            today,
            model=model,
            budget_seconds=budget_seconds,
            ledger=ledger,
            recent_contact_days=recent_contact_days,
        )
        for request in read_requests(queries)
    ]
    _write(out, [a.line for a in answers])
    if stats_out is not None:
        _write(stats_out, [a.stats for a in answers])
    return answers
