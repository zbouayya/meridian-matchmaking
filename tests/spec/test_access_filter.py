"""SEC-01 — the access policy is applied in code, before anything is ranked.

The scorer that came with the case is the oracle for "may this user see this record".
"""

from __future__ import annotations

from datetime import date

import pytest

from matchmaker import access
from matchmaker.corpus import load
from tests.spec.conftest import PACK_DIR
from tests.spec.oracle import Oracle


@pytest.mark.spec("SEC-01")
@pytest.mark.parametrize("user_id", ["U-01", "U-02", "U-03", "U-04", "U-05"])
def test_no_record_the_scorer_calls_hidden_reaches_a_ranker(oracle: Oracle, user_id: str) -> None:
    corpus = load(PACK_DIR)
    offered = access.candidates(corpus, corpus.users[user_id], today=date(2026, 11, 25))
    assert offered
    leaked = [r.id for r in offered if not oracle.can_see(oracle.users[user_id], r.id)]
    assert leaked == []
