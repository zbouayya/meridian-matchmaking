"""The two limits on who is suggested: a recent contact, and a person suggested too often.

Both are filters in code, applied before the ranking. First on small hand-built networks,
then on the pack through the whole pipeline, with no model.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from matchmaker import limits, pipeline, ranking, taxonomy
from matchmaker.baseline import read_requests
from matchmaker.corpus import ORGANIZATION, PERSON, Corpus, Edge, Record, User, load

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
QUERIES = PACK / "eval" / "queries_public.jsonl"
TODAY = date(2026, 11, 25)


def person(record_id: str, visibility: str = "public", org: str | None = None) -> Record:
    return Record(record_id, PERSON, record_id, visibility, org, False, (), (), "")


def edge(source: str, target: str, when: str, visibility: str = "public") -> Edge:
    return Edge(f"E-{source}-{target}", source, target, "worked_with", 3, when, visibility, "", "")


def network(edges: list[Edge], hidden: tuple[str, ...] = ()) -> Corpus:
    ids = {i for e in edges for i in (e.source, e.target)}
    records = {i: person(i, "restricted" if i in hidden else "public") for i in ids}
    return Corpus(records, {}, {}, tuple(edges))


def member(person_id: str | None = "A") -> User:
    return User("U-test", "members", person_id, None)


def kept(corpus: Corpus, user: User, **options: object) -> list[str]:
    records = [r for i, r in sorted(corpus.records.items()) if i != user.person_id]
    return [r.id for r in limits.apply(corpus, user, records, TODAY, **options).kept]  # type: ignore[arg-type]


# --- recent contact ---------------------------------------------------------------------


@pytest.mark.spec("REL-04", "FUN-07")
def test_a_person_met_within_the_window_is_not_suggested() -> None:
    corpus = network([edge("A", "B", "2026-10-15"), edge("A", "C", "2026-06-30")])
    assert limits.recent_contacts(corpus, member(), TODAY) == {"B": "2026-10-15"}
    assert kept(corpus, member()) == ["C"]


def test_the_window_counts_back_from_the_day_of_the_request() -> None:
    corpus = network([edge("A", "B", "2026-08-27"), edge("A", "C", "2026-08-26")])
    # 90 days before 25 November 2026 is 27 August 2026: that day is still inside.
    assert kept(corpus, member()) == ["C"]
    assert kept(corpus, member(), days=30) == ["B", "C"]


def test_the_latest_of_several_relationships_decides() -> None:
    corpus = network([edge("A", "B", "2024-01-01"), edge("B", "A", "2026-11-01")])
    assert kept(corpus, member()) == []


def test_zero_days_turns_the_limit_off() -> None:
    corpus = network([edge("A", "B", "2026-11-20")])
    assert kept(corpus, member(), days=0) == ["B"]


def test_a_requester_with_no_person_record_has_no_recent_contact() -> None:
    corpus = network([edge("A", "B", "2026-11-20")])
    assert limits.recent_contacts(corpus, member(None), TODAY) == {}
    assert kept(corpus, member(None)) == ["A", "B"]


def test_a_relationship_the_requester_may_not_see_is_not_used() -> None:
    # Nothing hidden may change an answer, not even by leaving someone out.
    corpus = network([edge("A", "B", "2026-11-20", visibility="staff")])
    assert kept(corpus, member()) == ["B"]


def test_a_date_that_cannot_be_read_is_not_counted() -> None:
    corpus = network([edge("A", "B", "last week")])
    assert kept(corpus, member()) == ["B"]


def test_a_recent_contact_also_removes_the_persons_other_record() -> None:
    corpus = network([edge("A", "B", "2026-11-20")])
    twin = replace(person("B2", org="O-1"), name="Rafael Ortega Ruiz")
    records = {
        **corpus.records,
        "B": replace(person("B", org="O-1"), name="Rafael Ortega"),
        "B2": twin,
    }
    corpus = replace(corpus, records=records)
    assert kept(corpus, member()) == []


# --- repetition -------------------------------------------------------------------------


@pytest.mark.spec("REL-03")
def test_a_person_suggested_often_enough_is_not_suggested_again() -> None:
    corpus = network([edge("B", "C", "2020-01-01")])
    ledger = limits.Ledger(limit=2)
    ledger.record([corpus.records["B"]])
    assert kept(corpus, member(), ledger=ledger) == ["B", "C"]
    ledger.record([corpus.records["B"]])
    assert kept(corpus, member(), ledger=ledger) == ["C"]


def test_only_people_are_counted() -> None:
    forum = Record("O-1", ORGANIZATION, "Forum", "public", None, False, (), (), "")
    ledger = limits.Ledger(limit=1)
    ledger.record([forum, forum])
    assert ledger.reached() == frozenset()
    corpus = Corpus({"O-1": forum}, {})
    assert limits.apply(corpus, member(None), [forum], TODAY, ledger).kept == [forum]


def test_a_limit_of_zero_turns_repetition_off() -> None:
    corpus = network([edge("B", "C", "2020-01-01")])
    ledger = limits.Ledger(limit=0)
    ledger.record([corpus.records["B"]] * 5)
    assert kept(corpus, member(), ledger=ledger) == ["B", "C"]


# --- on the pack, through the pipeline --------------------------------------------------


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load(PACK)


def run(corpus: Corpus, **options: int) -> dict[str, list[str]]:
    """The ids suggested for each public request, in the order of the file."""
    ranker = ranking.make_ranker(
        ranking.Options(synonyms=True, theme_boost=True), taxonomy.load(PACK)
    )
    ledger = limits.Ledger(options.get("max_suggestions", limits.MAX_SUGGESTIONS))
    days = options.get("recent_contact_days", limits.RECENT_CONTACT_DAYS)
    out: dict[str, list[str]] = {}
    for request in read_requests(QUERIES):
        answered = pipeline.answer(
            corpus, request, ranker, None, TODAY, ledger=ledger, recent_contact_days=days
        )
        out[request.query_id] = [r["id"] for r in answered.line["results"]]
    return out


@pytest.mark.spec("REL-04", "FUN-07")
def test_on_the_pack_a_member_is_not_offered_someone_they_met_last_month(corpus: Corpus) -> None:
    # U-03 is person P-005, who was in touch with P-001 on 15 October 2026.
    user = corpus.users["U-03"]
    assert limits.recent_contacts(corpus, user, TODAY).get("P-001") == "2026-10-15"
    without = run(corpus, recent_contact_days=0, max_suggestions=0)
    assert "P-001" in without["Q01"]
    assert "P-001" not in run(corpus)["Q01"]


@pytest.mark.spec("REL-03")
def test_on_the_pack_no_person_is_suggested_more_often_than_the_limit(corpus: Corpus) -> None:
    for limit in (1, 2):
        suggested = [
            i
            for ids in run(corpus, max_suggestions=limit).values()
            for i in ids
            if i.startswith("P-")
        ]
        assert max(suggested.count(i) for i in set(suggested)) <= limit


def test_the_run_statistics_say_who_was_left_out(corpus: Corpus) -> None:
    request = next(r for r in read_requests(QUERIES) if r.query_id == "Q01")
    answered = pipeline.answer(corpus, request, None, None, TODAY)
    assert "P-001" in answered.stats["left_out"]["recent_contact"]
    assert "left_out" not in answered.line
