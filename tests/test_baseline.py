"""The keyword search, and the baseline run on the pack's public requests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from matchmaker import baseline, cli, dedupe, keyword, ranking, taxonomy
from matchmaker.corpus import KINDS, ORGANIZATION, PERSON, Record, load
from tests.spec import checks
from tests.spec.oracle import SECRETARIAT_RULES_FILE, Oracle, load_oracle, run_scorer

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
QUERIES = PACK / "eval" / "queries_public.jsonl"
TODAY = date(2026, 11, 25)


def person(record_id: str, body: str, themes: tuple[str, ...] = ()) -> Record:
    return Record(record_id, PERSON, record_id, "public", None, False, themes, (), body)


def test_words_lose_their_case_accents_and_stopwords() -> None:
    assert keyword.tokens("Recherche d'experts en Hydrogène vert") == [
        "recherche",
        "experts",
        "hydrogene",
        "vert",
    ]


def test_the_record_sharing_the_rarest_words_comes_first() -> None:
    records = [
        person("P-1", "Works on water and trade."),
        person("P-2", "Builds hydrogen export corridors."),
        person("P-3", "Works on trade and logistics."),
    ]
    ranked = keyword.rank("hydrogen corridors and trade", records)
    assert [m.record.id for m in ranked] == ["P-2", "P-1", "P-3"]
    assert ranked[0].terms == ("hydrogen", "corridors")


def test_a_record_sharing_no_word_is_not_returned() -> None:
    assert keyword.rank("ocean finance", [person("P-1", "Works on trade.")]) == []


def test_theme_tags_are_searched_as_words_only_when_switched_on() -> None:
    tagged = [person("P-1", "A short profile.", themes=("green-hydrogen",))]
    assert keyword.rank("hydrogen", tagged) == []
    assert [m.record.id for m in keyword.rank("hydrogen", tagged, with_tags=True)] == ["P-1"]


def test_a_related_word_counts_for_less_than_a_word_of_the_request() -> None:
    records = [person("P-1", "Hydrogen."), person("P-2", "Ammonia.")]
    ranked = keyword.rank("hydrogen", records, related=["ammonia"])
    assert [m.record.id for m in ranked] == ["P-1", "P-2"]
    assert ranked[1].terms == () and ranked[1].related == ("ammonia",)


@pytest.fixture(scope="module")
def themes() -> taxonomy.Taxonomy:
    return taxonomy.load(PACK)


def test_a_theme_is_recognised_in_any_of_the_three_languages(themes: taxonomy.Taxonomy) -> None:
    assert taxonomy.themes_in("Recherche d'experts en hydrogène vert", themes) == (
        "green-hydrogen",
    )
    assert taxonomy.themes_in("Expertos en hidrógeno verde", themes) == ("green-hydrogen",)
    assert taxonomy.themes_in("AI governance and cybersecurity", themes) == (
        "ai-governance",
        "cybersecurity",
    )
    assert taxonomy.themes_in("Someone who likes sailing", themes) == ()


@pytest.mark.spec("REL-01")
def test_synonyms_carry_a_french_request_to_an_english_profile(
    themes: taxonomy.Taxonomy,
) -> None:
    records = [person("P-1", "Builds green hydrogen export corridors.")]
    request = "Recherche d'experts en hydrogène vert"
    assert ranking.rank(request, records, ranking.Options(), themes) == []
    found = ranking.rank(request, records, ranking.Options(synonyms=True), themes)
    assert [m.record.id for m in found] == ["P-1"]
    assert found[0].terms == ()
    assert {"green", "hydrogen"} <= set(found[0].related)
    assert ranking.describe(found[0]).startswith("Related words: ")


def test_the_theme_boost_moves_a_tagged_record_up_but_never_adds_one(
    themes: taxonomy.Taxonomy,
) -> None:
    records = [
        person("P-1", "Green hydrogen, green hydrogen, green hydrogen."),
        person("P-2", "Green hydrogen.", themes=("green-hydrogen",)),
        person("P-3", "Nothing in common.", themes=("green-hydrogen",)),
    ]
    plain = ranking.rank("green hydrogen", records, ranking.Options(), themes)
    boosted = ranking.rank("green hydrogen", records, ranking.Options(theme_boost=True), themes)
    assert [m.record.id for m in plain] == ["P-1", "P-2"]
    assert [m.record.id for m in boosted] == ["P-2", "P-1"]
    assert boosted[0].themes == ("green-hydrogen",)


def test_the_stale_copy_of_a_person_is_dropped() -> None:
    def colleague(record_id: str, name: str, engaged: str) -> Record:
        return Record(
            record_id, PERSON, name, "members", "O-07", False, (), (name,), "", last_engaged=engaged
        )

    old = colleague("P-041", "Rafael Ortega", "2024-05-20")
    current = colleague("P-023", "Rafael Ortega Ruiz", "2026-09-03")
    other = colleague("P-009", "Ana Costa", "2026-01-01")
    assert dedupe.same_person(old, current)
    assert not dedupe.same_person(old, other)
    merged = dedupe.merge_duplicates([old, other, current])
    assert [r.id for r in merged] == ["P-009", "P-023"]
    assert "Rafael Ortega" in merged[1].fields  # the stale copy stays searchable


def test_the_packs_known_duplicate_is_found_by_the_rule() -> None:
    records = load(PACK).records
    assert dedupe.same_person(records["P-023"], records["P-041"])
    people = [r for r in records.values() if r.kind == PERSON]
    assert len(people) - len(dedupe.merge_duplicates(people)) == 1


def test_a_record_with_no_free_text_is_searched_by_its_themes() -> None:
    organisation = Record(
        "O-1", ORGANIZATION, "Sahara Solar", "public", None, False, ("green-hydrogen",), (), ""
    )
    profile = person("P-1", "A short profile.", themes=("green-hydrogen",))
    assert [m.record.id for m in keyword.rank("hydrogen", [organisation, profile])] == ["O-1"]


def test_a_request_that_names_no_kind_gets_all_three_and_is_told_so(tmp_path: Path) -> None:
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        '{"query_id": "X1", "user_id": "U-03", "query": "green hydrogen"}\n'
        '{"query_id": "X2", "user_id": "U-03", "query": "green hydrogen",'
        ' "entity_types": ["initiative"]}\n',
        encoding="utf-8",
    )
    open_request, narrow_request = baseline.read_requests(queries)
    assert open_request.entity_types == KINDS and not open_request.kinds_stated
    assert narrow_request.entity_types == ("initiative",) and narrow_request.kinds_stated
    first, second = baseline.run(PACK, queries, tmp_path / "out.jsonl", today=TODAY)
    assert first["note"] == baseline.ALL_KINDS_NOTE
    assert "note" not in second
    assert {r["id"][0] for r in second["results"]} == {"I"}


def test_requests_are_read_without_their_labels() -> None:
    requests = baseline.read_requests(QUERIES)
    assert len(requests) == 10
    assert not hasattr(requests[0], "relevance")


@pytest.fixture(scope="module")
def oracle() -> Oracle:
    return load_oracle(PACK)


ALL_OPTIONS = [
    ranking.Options(),
    ranking.Options(tags=True),
    ranking.Options(synonyms=True, theme_boost=True),
]


@pytest.fixture(scope="module", params=ALL_OPTIONS, ids=["keyword", "tags", "boosted"])
def lines(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, list[dict[str, Any]]]:
    """Every ranking option goes through the same access filter, so each is held to it."""
    out = tmp_path_factory.mktemp("baseline") / "baseline.jsonl"
    return out, baseline.run(PACK, QUERIES, out, options=request.param, today=TODAY)


def test_the_baseline_answers_in_the_documented_format(
    lines: tuple[Path, list[dict[str, Any]]],
) -> None:
    for line in lines[1]:
        assert checks.format_violations(line) == []
        assert checks.size_violations(line) == []
        assert checks.latency_violations(line) == []
        assert checks.evidence_violations(line) == []


def test_the_baseline_breaks_no_access_rule(
    oracle: Oracle, lines: tuple[Path, list[dict[str, Any]]]
) -> None:
    for line in lines[1]:
        user = oracle.user_for(line["query_id"])
        assert user is not None
        assert checks.access_violations(oracle, user, line) == []
        assert checks.self_match_violations(oracle, user, line) == []
        assert checks.secretariat_staff_violations(oracle, line) == []
        assert checks.secretariat_rule_violations(oracle, user, line) == []


def test_the_baseline_passes_the_scorers_security_gate(
    oracle: Oracle, lines: tuple[Path, list[dict[str, Any]]]
) -> None:
    card = run_scorer(oracle, lines[0], rules=SECRETARIAT_RULES_FILE)
    assert card.gate_passed
    assert (card.access_violations, card.self_org, card.rule_breaks, card.missing) == (0, 0, 0, 0)
    assert card.duplicates == 0


def test_an_unknown_user_is_offered_nothing(tmp_path: Path) -> None:
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        '{"query_id": "X1", "user_id": "U-99", "query": "hydrogen"}\n', encoding="utf-8"
    )
    lines = baseline.run(PACK, queries, tmp_path / "out.jsonl", today=TODAY)
    assert lines[0]["results"] == []


def test_the_baseline_command_writes_one_line_per_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "results" / "baseline.jsonl"
    assert cli.main(["baseline", "--pack", str(PACK), "--out", str(out)]) == cli.EXIT_OK
    assert len(out.read_text(encoding="utf-8").splitlines()) == 10
    assert "requests 10" in capsys.readouterr().out
