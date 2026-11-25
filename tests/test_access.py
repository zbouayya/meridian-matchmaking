"""The access filter, rule by rule.

The comparison with the scorer that came with the case is in
`tests/spec/test_access_filter.py` (SEC-01). The rules the scorer does not document — the
Secretariat's pause and do-not-pair — are checked here directly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from matchmaker import access
from matchmaker.corpus import PERSON, Corpus, load

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
BEFORE_THE_PAUSE_ENDS = date(2026, 11, 25)
AFTER_THE_PAUSE_ENDS = date(2027, 4, 1)
USERS = ("U-01", "U-02", "U-03", "U-04", "U-05")


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load(PACK)


def offered(corpus: Corpus, user_id: str, today: date = BEFORE_THE_PAUSE_ENDS) -> set[str]:
    return {r.id for r in access.candidates(corpus, corpus.users[user_id], today=today)}


def test_the_pack_is_loaded_whole(corpus: Corpus) -> None:
    kinds = [r.kind for r in corpus.records.values()]
    assert (kinds.count(PERSON), len(kinds), len(corpus.users)) == (50, 87, 5)


@pytest.mark.spec("HAR-04")
def test_each_step_up_the_ladder_only_adds_records(corpus: Corpus) -> None:
    guest, staff, office = (
        {r.id for r in corpus.records.values() if access.can_see(corpus.users[u], r)}
        for u in ("U-05", "U-02", "U-01")
    )
    assert guest < staff < office


def test_an_opted_out_person_is_hidden_below_staff_and_flagged_to_staff(corpus: Corpus) -> None:
    opted_out = next(r for r in corpus.records.values() if r.opt_out)
    assert opted_out.id not in offered(corpus, "U-03")
    assert opted_out.id not in offered(corpus, "U-05")
    assert opted_out.id in offered(corpus, "U-02")
    staff_flag = access.flag(corpus.users["U-02"], opted_out, BEFORE_THE_PAUSE_ENDS)
    assert staff_flag == "Flag: opted out of matchmaking."
    assert access.flag(corpus.users["U-03"], opted_out, BEFORE_THE_PAUSE_ENDS) == ""


def test_nobody_is_offered_themselves_or_their_own_organisation(corpus: Corpus) -> None:
    for user in corpus.users.values():
        for record in access.candidates(corpus, user, today=BEFORE_THE_PAUSE_ENDS):
            assert record.id not in (user.person_id, user.org_id)
            assert record.org_id is None or record.org_id != user.org_id


@pytest.mark.parametrize("user_id", USERS)
def test_secretariat_staff_are_never_offered(corpus: Corpus, user_id: str) -> None:
    secretariat = {r.id for r in corpus.records.values() if r.org_id == access.SECRETARIAT_ORG}
    assert secretariat
    assert not secretariat & offered(corpus, user_id)


@pytest.mark.parametrize("user_id", ["U-03", "U-04", "U-05"])
def test_a_paused_person_is_never_offered_to_a_member_or_a_guest(
    corpus: Corpus, user_id: str
) -> None:
    assert "P-042" not in offered(corpus, user_id, BEFORE_THE_PAUSE_ENDS)
    paused = corpus.records["P-042"]
    assert access.flag(corpus.users[user_id], paused, BEFORE_THE_PAUSE_ENDS) == ""


@pytest.mark.parametrize("user_id", ["U-01", "U-02"])
def test_staff_see_a_paused_person_with_the_pause_stated(corpus: Corpus, user_id: str) -> None:
    assert "P-042" in offered(corpus, user_id, BEFORE_THE_PAUSE_ENDS)
    said = access.flag(corpus.users[user_id], corpus.records["P-042"], BEFORE_THE_PAUSE_ENDS)
    assert said == "Flag: paused until 31 March 2027, ask before any introduction."


def test_the_pause_ends_on_its_date(corpus: Corpus) -> None:
    assert "P-042" in offered(corpus, "U-03", AFTER_THE_PAUSE_ENDS)
    staff = corpus.users["U-01"]
    assert access.flag(staff, corpus.records["P-042"], AFTER_THE_PAUSE_ENDS) == ""


def test_two_people_who_must_not_be_paired_are_not_offered_to_each_other(corpus: Corpus) -> None:
    # U-04 is P-027; U-03 is someone else and is not concerned by the rule.
    assert "P-050" not in offered(corpus, "U-04")
    assert "P-050" in offered(corpus, "U-03")


def test_the_organisation_of_one_is_not_offered_to_the_other_either(corpus: Corpus) -> None:
    # P-050 belongs to O-25: offering it to U-04 as a partner would pair them all the same.
    assert corpus.records["P-050"].org_id == "O-25"
    assert "O-25" not in offered(corpus, "U-04")
    assert "O-25" in offered(corpus, "U-03")


def test_an_unknown_visibility_is_the_most_closed_level() -> None:
    assert access.level("TOP SECRET") == access.CLEARANCE["restricted"]
