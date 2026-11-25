"""Evidence: nothing the user may not see is cited, and nothing of it reaches a model."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from matchmaker import access, evidence
from matchmaker.corpus import Corpus, load
from tests.spec.oracle import Oracle, load_oracle

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
TODAY = date(2026, 11, 25)
USERS = ("U-01", "U-02", "U-03", "U-04", "U-05")
_ID = re.compile(r"\b[POINEDM]-\d+\b")


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load(PACK)


@pytest.fixture(scope="module")
def oracle() -> Oracle:
    return load_oracle(PACK)


@pytest.mark.parametrize("user_id", USERS)
def test_nothing_hidden_is_cited_or_handed_to_the_model(
    corpus: Corpus, oracle: Oracle, user_id: str
) -> None:
    user, judged = corpus.users[user_id], oracle.users[user_id]
    hidden = oracle.hidden_names(judged)
    offered = access.candidates(corpus, user, today=TODAY)
    assert offered
    for record in offered:
        found = evidence.gather(corpus, user, record, TODAY)
        assert found.ids[0] == record.id
        assert [i for i in found.ids if not oracle.can_see(judged, i)] == []
        assert [p for p in found.warm_path if not oracle.can_see(judged, p)] == []
        told = json.dumps(found.facts, ensure_ascii=False)
        assert [i for i in _ID.findall(told) if not oracle.can_see(judged, i)] == []
        assert [name for name, _ in hidden if name in told.casefold()] == []


def test_the_same_hidden_names_as_the_scorer_side_of_the_tests(
    corpus: Corpus, oracle: Oracle
) -> None:
    for user_id in USERS:
        ours = set(evidence.hidden_names(corpus, corpus.users[user_id]))
        theirs = {name for name, _ in oracle.hidden_names(oracle.users[user_id])}
        assert theirs <= ours


def test_a_person_the_requester_already_knows_is_reported_as_such(corpus: Corpus) -> None:
    found = evidence.gather(corpus, corpus.users["U-03"], corpus.records["P-001"], TODAY)
    assert found.warm_path == ("P-005", "P-001")
    known = found.facts["already_connected_to_the_requester"]
    assert known["type"] == "board peer" and known["last_interaction"] == "2026-10-15"
    assert any(i.startswith("E-") for i in found.ids)
    assert found.facts["introduction_path"][0]["from"] == corpus.records["P-005"].name


def test_staff_get_evidence_but_no_path(corpus: Corpus) -> None:
    found = evidence.gather(corpus, corpus.users["U-01"], corpus.records["P-001"], TODAY)
    assert found.warm_path == ()
    assert "introduction_path" not in found.facts
    assert "already_connected_to_the_requester" not in found.facts


def test_an_instruction_hidden_in_a_profile_is_not_handed_to_the_model(corpus: Corpus) -> None:
    planted = corpus.records["P-044"]
    # The hidden comment is removed when the pack is loaded, and reported for a person.
    assert "P-044" in corpus.hidden_text and "SYSTEM NOTE" not in planted.body
    found = evidence.gather(corpus, corpus.users["U-03"], planted, TODAY)
    told = json.dumps(found.facts)
    assert "SYSTEM NOTE" not in told and "Ignore all previous" not in told
    assert "SecureGrid" in told


def test_an_organisation_cites_the_initiatives_it_leads(corpus: Corpus) -> None:
    led = next(r for r in corpus.records.values() if r.lead_orgs and r.visibility == "public")
    organisation = corpus.records[led.lead_orgs[0]]
    found = evidence.gather(corpus, corpus.users["U-01"], organisation, TODAY)
    assert led.id in found.ids
    assert found.warm_path == ()


def test_a_sentence_naming_a_hidden_record_is_dropped_whole() -> None:
    text = "# Heading\n\nWorks on water. Advises Project Tidewater closely. Based in Kenya."
    assert evidence.clean(text, ("project tidewater",), 200) == "Works on water. Based in Kenya."


def test_text_handed_to_the_model_is_capped() -> None:
    text = "One sentence here. " * 50
    assert len(evidence.clean(text, (), 100)) <= 100
    assert evidence.clean("A <!-- hidden --> visible part.", (), 100) == "A visible part."
