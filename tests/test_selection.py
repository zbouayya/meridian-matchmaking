"""Selection by a model, tested with a fake model: what it may change and what it may not."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import anthropic
import httpx2
import pytest

from matchmaker import access, dedupe, evidence, ranking, selection, tables, taxonomy
from matchmaker.corpus import Corpus, Record, load
from matchmaker.keyword import Match

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
TODAY = date(2026, 11, 25)
OPTIONS = ranking.Options(synonyms=True, theme_boost=True)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load(PACK)


@pytest.fixture(scope="module")
def rank_all() -> selection.RankAll:
    themes = taxonomy.load(PACK)

    def ranked(query: str, records: Any) -> list[Match]:
        return ranking.rank(query, records, OPTIONS, themes, limit=max(len(records), 1))

    return ranked


def pool_of(corpus: Corpus, user_id: str) -> list[Record]:
    offered = access.candidates(corpus, corpus.users[user_id], today=TODAY)
    return dedupe.merge_duplicates(offered)


def model(
    answer: Any = None, failure: Exception | None = None
) -> tuple[anthropic.Anthropic, list[str]]:
    prompts: list[str] = []

    def create(**request: Any) -> Any:
        prompts.append(request["messages"][0]["content"])
        if failure is not None:
            raise failure
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=7_000, output_tokens=30),
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return cast(anthropic.Anthropic, client), prompts


def test_the_models_choice_and_order_are_used(corpus: Corpus, rank_all: selection.RankAll) -> None:
    client, _ = model({"ids": ["P-040", "I-01"]})
    ranker = selection.ModelRanker(client, rank_all)
    chosen = ranker("green hydrogen", pool_of(corpus, "U-03"))
    assert [m.record.id for m in chosen] == ["P-040", "I-01"]
    assert ranker.last["by"] == "model" and ranker.last["cost_usd"] == pytest.approx(0.000715)


def test_an_id_outside_the_table_is_dropped(corpus: Corpus, rank_all: selection.RankAll) -> None:
    # P-012 is restricted and P-999 does not exist: a member's table holds neither.
    client, _ = model({"ids": ["P-012", "P-999", "P-040", "P-040"]})
    ranker = selection.ModelRanker(client, rank_all)
    chosen = ranker("green hydrogen", pool_of(corpus, "U-03"))
    assert [m.record.id for m in chosen] == ["P-040"]
    assert ranker.last["dropped_ids"] == 3


def test_never_more_than_five(corpus: Corpus, rank_all: selection.RankAll) -> None:
    pool = pool_of(corpus, "U-03")
    client, _ = model({"ids": [r.id for r in pool[:9]]})
    assert len(selection.ModelRanker(client, rank_all)("green hydrogen", pool)) == 5


@pytest.mark.parametrize(
    "failure",
    [
        anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x.example")),
        anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x.example")),
        TypeError('"Could not resolve authentication method."'),
    ],
)
def test_a_failed_call_gives_the_rule_based_ranking(
    corpus: Corpus, rank_all: selection.RankAll, failure: Exception
) -> None:
    pool = pool_of(corpus, "U-03")
    client, _ = model(failure=failure)
    ranker = selection.ModelRanker(client, rank_all)
    chosen = ranker("green hydrogen", pool)
    assert [m.record.id for m in chosen] == [
        m.record.id for m in rank_all("green hydrogen", pool)[:5]
    ]
    assert ranker.last["by"] == "rules" and ranker.last["fallback_reason"]


def test_an_answer_that_cannot_be_read_gives_the_rule_based_ranking(
    corpus: Corpus, rank_all: selection.RankAll
) -> None:
    pool = pool_of(corpus, "U-03")
    client, _ = model("I would rather not say.")
    ranker = selection.ModelRanker(client, rank_all)
    assert ranker("green hydrogen", pool) == rank_all("green hydrogen", pool)[:5]
    assert ranker.last["by"] == "rules"


def test_an_empty_choice_is_a_valid_answer(corpus: Corpus, rank_all: selection.RankAll) -> None:
    client, _ = model({"ids": []})
    ranker = selection.ModelRanker(client, rank_all)
    assert ranker("underwater basket weaving", pool_of(corpus, "U-03")) == []
    assert ranker.last["by"] == "model"


@pytest.mark.parametrize("user_id", ["U-01", "U-02", "U-03", "U-04", "U-05"])
def test_the_table_shown_to_the_model_holds_nothing_hidden_and_no_access_field(
    corpus: Corpus, rank_all: selection.RankAll, user_id: str
) -> None:
    user = corpus.users[user_id]
    hidden = evidence.hidden_names(corpus, user)
    client, prompts = model({"ids": []})
    ranker = selection.ModelRanker(client, rank_all, forbidden=hidden)
    ranker("green hydrogen", pool_of(corpus, user_id))
    shown = prompts[0].casefold()
    assert not any(name in shown for name in hidden)
    for line in prompts[0].split("<candidates>\n")[1].split("\n</candidates>")[0].splitlines():
        row = json.loads(line)
        assert access.can_see(user, corpus.records[row["id"]])
        assert not {"visibility", "opt_out", "opt_out_matchmaking"} & set(row)


def test_a_row_carries_what_a_record_does_and_nothing_about_access(corpus: Corpus) -> None:
    row = tables.row(corpus.records["P-001"])
    assert set(row) == {
        "id",
        "kind",
        "name",
        "title",
        "organisation",
        "country",
        "regions",
        "themes",
        "about",
    }
    assert len(row["about"]) <= tables.ABOUT_CHARS


def test_the_tables_are_written_whole(corpus: Corpus, tmp_path: Path) -> None:
    written = tables.write(corpus, tmp_path)
    assert [p.name for p in written] == [
        "people.csv",
        "organisations.csv",
        "initiatives.csv",
        "notes.csv",
    ]
    lines = [len(p.read_text(encoding="utf-8").splitlines()) - 1 for p in written]
    assert lines == [50, 25, 12, 9]
