"""The explicit requirements, checked on the system's output.

These tests read `results/results.jsonl` (or the file named by MERIDIAN_RESULTS). Until that
file exists they are skipped, and the spec report lists their specs as waiting. They judge
the output only, so they hold whatever the system behind it looks like.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.spec import checks
from tests.spec.oracle import Oracle, Scorecard, User

Line = dict[str, Any]

END_TO_END_LIMIT_MS = 4000  # SPD-02


def per_line(
    oracle: Oracle, results: list[Line], check: Callable[[User, Line], list[str]]
) -> list[str]:
    found: list[str] = []
    for line in results:
        query_id = str(line.get("query_id"))
        user = oracle.user_for(query_id)
        if user is None:
            found.append(f"{query_id}: not a request of {oracle.queries_path.name}")
            continue
        found += [f"{query_id}: {violation}" for violation in check(user, line)]
    return found


def listed(found: list[str]) -> str:
    return f"{len(found)} violation(s):\n" + "\n".join(found)


@pytest.mark.spec("FUN-11")
def test_every_request_is_answered_exactly_once(oracle: Oracle, results: list[Line]) -> None:
    answered = sorted(str(line.get("query_id")) for line in results)
    assert answered == sorted(oracle.queries)


@pytest.mark.spec("FUN-09")
def test_the_output_follows_the_documented_format(results: list[Line]) -> None:
    found = [
        f"{line.get('query_id')}: {v}" for line in results for v in checks.format_violations(line)
    ]
    assert not found, listed(found)


@pytest.mark.spec("FUN-01")
def test_at_most_five_matches_per_request(results: list[Line]) -> None:
    found = [
        f"{line.get('query_id')}: {v}" for line in results for v in checks.size_violations(line)
    ]
    assert not found, listed(found)


@pytest.mark.spec("SEC-12", "SEC-02")
def test_the_security_gate_passes(scorecard: Scorecard) -> None:
    assert scorecard.gate_passed, scorecard.raw
    assert scorecard.access_violations == 0, scorecard.raw


@pytest.mark.spec("SEC-02", "SEC-05")
def test_nothing_above_the_users_clearance(oracle: Oracle, results: list[Line]) -> None:
    found = per_line(
        oracle, results, lambda user, line: checks.access_violations(oracle, user, line)
    )
    assert not found, listed(found)


@pytest.mark.spec("FUN-04", "SEC-03")
def test_warm_paths_are_chains_of_visible_edges(
    oracle: Oracle, results: list[Line], scorecard: Scorecard
) -> None:
    found = per_line(
        oracle, results, lambda user, line: checks.warm_path_violations(oracle, user, line)
    )
    assert not found, listed(found)
    if scorecard.warm_paths is not None:
        valid, given = scorecard.warm_paths
        assert valid == given, scorecard.raw


@pytest.mark.spec("FUN-03", "REL-05")
def test_every_match_cites_evidence_that_exists(
    oracle: Oracle, results: list[Line], scorecard: Scorecard
) -> None:
    found = [
        f"{line.get('query_id')}: {v}" for line in results for v in checks.evidence_violations(line)
    ]
    found += [
        f"{line.get('query_id')}: {v}"
        for line in results
        for v in checks.existence_violations(oracle, line)
    ]
    assert not found, listed(found)
    if scorecard.evidence is not None:
        grounded, cited = scorecard.evidence
        assert grounded == cited, scorecard.raw


@pytest.mark.spec("SEC-07")
def test_no_self_match_and_no_own_organisation(
    oracle: Oracle, results: list[Line], scorecard: Scorecard
) -> None:
    found = per_line(
        oracle, results, lambda user, line: checks.self_match_violations(oracle, user, line)
    )
    assert not found, listed(found)
    assert scorecard.self_org == 0, scorecard.raw


@pytest.mark.spec("REL-02")
def test_no_person_appears_twice(oracle: Oracle, results: list[Line], scorecard: Scorecard) -> None:
    found = [
        f"{line.get('query_id')}: {v}"
        for line in results
        for v in checks.duplicate_violations(oracle, line)
    ]
    assert not found, listed(found)
    assert scorecard.duplicates == 0, scorecard.raw


@pytest.mark.spec("SEC-09")
def test_secretariat_staff_are_not_recommended(oracle: Oracle, results: list[Line]) -> None:
    found = [
        f"{line.get('query_id')}: {v}"
        for line in results
        for v in checks.secretariat_staff_violations(oracle, line)
    ]
    assert not found, listed(found)


@pytest.mark.spec("SEC-10")
def test_secretariat_introduction_rules_hold(
    oracle: Oracle, results: list[Line], scorecard: Scorecard
) -> None:
    found = per_line(
        oracle, results, lambda user, line: checks.secretariat_rule_violations(oracle, user, line)
    )
    assert not found, listed(found)
    assert scorecard.rule_breaks == 0, scorecard.raw


@pytest.mark.spec("SEC-08")
def test_planted_instructions_are_not_obeyed(results: list[Line], scorecard: Scorecard) -> None:
    assert scorecard.injection_signals == 0, scorecard.raw
    found = [
        f"{line.get('query_id')}: {v}"
        for line in results
        for v in checks.injection_echo_violations(line)
    ]
    assert not found, listed(found)


@pytest.mark.spec("SEC-06", "SEC-04")
def test_explanations_never_name_a_hidden_record(oracle: Oracle, results: list[Line]) -> None:
    found = per_line(
        oracle, results, lambda user, line: checks.hidden_mention_violations(oracle, user, line)
    )
    assert not found, listed(found)


@pytest.mark.spec("FUN-02")
def test_every_match_is_explained_in_one_or_two_sentences(results: list[Line]) -> None:
    found = [
        f"{line.get('query_id')}: {v}"
        for line in results
        for v in checks.explanation_violations(line)
    ]
    assert not found, listed(found)


@pytest.mark.spec("SPD-04")
def test_every_line_reports_its_latency(results: list[Line]) -> None:
    found = [
        f"{line.get('query_id')}: {v}" for line in results for v in checks.latency_violations(line)
    ]
    assert not found, listed(found)


@pytest.mark.spec("SPD-02")
def test_end_to_end_p95_is_under_four_seconds(scorecard: Scorecard) -> None:
    assert scorecard.latency_p95_ms is not None, "no latency reported:\n" + scorecard.raw
    assert scorecard.latency_p95_ms < END_TO_END_LIMIT_MS, scorecard.raw


@pytest.mark.spec("REL-06")
def test_relevance_is_measured_on_every_request(scorecard: Scorecard) -> None:
    # The brief sets no threshold. The numbers are in the spec report; what is enforced is
    # that they exist for all requests.
    assert scorecard.missing == 0, scorecard.raw
    assert 0.0 <= scorecard.ndcg <= 1.0
    assert 0.0 <= scorecard.precision <= 1.0
