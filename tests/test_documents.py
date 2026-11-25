"""Documents and emails as evidence, the classification rule, and the rules file."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from matchmaker import access, documents, evidence
from matchmaker.corpus import Corpus, load

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
TODAY = date(2026, 11, 25)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load(PACK)


@pytest.mark.parametrize(
    ("top", "level"),
    [
        (["MERIDIAN FORUM | Classification: PUBLIC", "Page 1"], "public"),
        (["Classification: RESTRICTED — MD OFFICE ONLY"], "restricted"),
        (["INTERNAL — STAFF ONLY", "Minutes"], "staff"),
        (["ANNUAL REPORT", "Classification: members"], "members"),
        (["PUBLIC SUMMARY — RESTRICTED ANNEX"], "restricted"),
        (["Classification: to be confirmed"], "restricted"),
        (["Public-private partnerships, a review"], "restricted"),
        ([], "restricted"),
    ],
)
def test_the_classification_is_read_from_the_top_or_the_file_is_closed(
    top: list[str], level: str
) -> None:
    assert documents.classification_of(top) == level


def test_a_name_is_looked_for_in_full_without_its_honorific() -> None:
    email = documents.load(PACK)["M-01"]
    assert documents.passages_naming(email, "Dr. Léa Fontaine")
    assert documents.passages_naming(email, "Hamza Rachidi")
    assert documents.passages_naming(email, "Léa") == []


def test_an_email_is_evidence_for_the_people_it_names_at_its_own_level(corpus: Corpus) -> None:
    person = corpus.records["P-017"]
    staff = evidence.gather(corpus, corpus.users["U-02"], person, TODAY)
    assert "M-01" in staff.ids
    # The public report names the same person, so both are cited to staff.
    assert [d["id"] for d in staff.facts["named_in"]] == ["D-01", "M-01"]
    member = evidence.gather(corpus, corpus.users["U-03"], person, TODAY)
    assert "M-01" not in member.ids
    assert [d["id"] for d in member.facts["named_in"]] == ["D-01"]


def test_a_public_report_cited_to_a_guest_names_nobody_they_cannot_see(corpus: Corpus) -> None:
    guest = corpus.users["U-05"]
    found = evidence.gather(corpus, guest, corpus.records["I-01"], TODAY)
    assert "D-01" in found.ids
    hidden = evidence.hidden_names(corpus, guest)
    text = " ".join(d["passage"] for d in found.facts["named_in"]).casefold()
    assert not any(name in text for name in hidden)


def test_the_rules_are_read_from_the_file_beside_the_pack() -> None:
    rules = access.load_rules(PACK.with_name(access.RULES_FILE))
    assert [(p.person_id, p.until) for p in rules.pauses] == [("P-042", date(2027, 3, 31))]
    assert [sorted(r.people) for r in rules.do_not_pair] == [["P-027", "P-050"]]
    assert rules == access.rules()


def test_a_rule_the_code_does_not_understand_stops_the_run(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"rules": [{"type": "mute", "sources": ["X"]}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown rule type"):
        access.load_rules(path)
    with pytest.raises(FileNotFoundError):
        access.load_rules(tmp_path / "missing.json")
