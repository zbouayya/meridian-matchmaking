"""Warm paths: only through relationships the requester may see, and through people who
may introduce."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from matchmaker import access, graph
from matchmaker.corpus import PERSON, Corpus, Edge, Record, User, load
from tests.spec.oracle import Oracle, load_oracle

PACK = Path(__file__).resolve().parents[1] / "data" / "meridian_case_pack"
TODAY = date(2026, 11, 25)
AFTER_THE_PAUSE = date(2027, 4, 1)


def person(record_id: str, visibility: str = "public") -> Record:
    return Record(record_id, PERSON, record_id, visibility, None, False, (), (), "")


def edge(
    edge_id: str,
    source: str,
    target: str,
    strength: int = 3,
    when: str = "2026-01-01",
    visibility: str = "public",
) -> Edge:
    return Edge(edge_id, source, target, "worked_with", strength, when, visibility, "", "")


def network(edges: list[Edge], hidden: tuple[str, ...] = ()) -> Corpus:
    ids = {i for e in edges for i in (e.source, e.target)}
    records = {i: person(i, "restricted" if i in hidden else "public") for i in ids}
    return Corpus(records, {}, {}, tuple(edges))


def member(person_id: str | None = "A", clearance: str = "members") -> User:
    return User("U-test", clearance, person_id, None)


def people(corpus: Corpus, user: User, target: str, today: date = TODAY) -> tuple[str, ...] | None:
    path = graph.warm_path(corpus, user, target, today)
    return None if path is None else path.people


def test_a_direct_relationship_is_the_whole_path() -> None:
    corpus = network([edge("E-1", "A", "B")])
    path = graph.warm_path(corpus, member(), "B", TODAY)
    assert path is not None
    assert (path.people, [e.id for e in path.edges]) == (("A", "B"), ["E-1"])


def test_an_edge_is_walked_in_either_direction() -> None:
    assert people(network([edge("E-1", "B", "A")]), member(), "B") == ("A", "B")


def test_the_shortest_path_wins_over_a_stronger_longer_one() -> None:
    corpus = network([edge("E-1", "A", "B", 1), edge("E-2", "A", "C", 5), edge("E-3", "C", "B", 5)])
    assert people(corpus, member(), "B") == ("A", "B")


def test_between_equal_lengths_the_stronger_weakest_link_wins() -> None:
    corpus = network(
        [
            edge("E-1", "A", "C", 5),
            edge("E-2", "C", "B", 1),
            edge("E-3", "A", "D", 3),
            edge("E-4", "D", "B", 3),
        ]
    )
    assert people(corpus, member(), "B") == ("A", "D", "B")


def test_between_equal_strengths_the_more_recent_wins() -> None:
    corpus = network(
        [
            edge("E-1", "A", "C", 3, "2024-01-01"),
            edge("E-2", "C", "B", 3, "2024-01-01"),
            edge("E-3", "A", "D", 3, "2026-06-01"),
            edge("E-4", "D", "B", 3, "2026-06-01"),
        ]
    )
    assert people(corpus, member(), "B") == ("A", "D", "B")


def test_the_strongest_of_two_relationships_between_the_same_people_is_cited() -> None:
    corpus = network([edge("E-1", "A", "B", 2), edge("E-2", "A", "B", 4)])
    path = graph.warm_path(corpus, member(), "B", TODAY)
    assert path is not None and [e.id for e in path.edges] == ["E-2"]


def test_a_path_is_never_longer_than_three_introductions() -> None:
    chain = [edge(f"E-{n}", a, b) for n, (a, b) in enumerate(zip("ABCDE", "BCDEF", strict=True))]
    corpus = network(chain)
    assert people(corpus, member(), "D") == ("A", "B", "C", "D")
    assert people(corpus, member(), "E") is None


def test_staff_and_guests_have_no_place_in_the_network_so_no_path() -> None:
    corpus = network([edge("E-1", "A", "B")])
    assert people(corpus, member(person_id=None, clearance="restricted"), "B") is None


def test_a_relationship_above_the_users_level_does_not_exist_for_them() -> None:
    corpus = network([edge("E-1", "A", "B", visibility="staff")])
    assert people(corpus, member(), "B") is None
    assert people(corpus, member(clearance="staff"), "B") == ("A", "B")


def test_a_hidden_person_cannot_stand_in_the_middle() -> None:
    corpus = network([edge("E-1", "A", "H"), edge("E-2", "H", "B")], hidden=("H",))
    assert people(corpus, member(), "B") is None
    assert graph.visible_edges(corpus, member()) == []


def test_a_paused_person_introduces_nobody_until_the_pause_ends() -> None:
    paused = access.rules().pauses[0].person_id
    corpus = network([edge("E-1", "A", paused), edge("E-2", paused, "B")])
    assert people(corpus, member(), "B", TODAY) is None
    assert people(corpus, member(), "B", AFTER_THE_PAUSE) == ("A", paused, "B")


def test_two_people_who_must_not_be_paired_are_not_routed_through_each_other() -> None:
    first, second = sorted(access.rules().do_not_pair[0].people)
    corpus = network([edge("E-1", first, second), edge("E-2", second, "B")])
    assert people(corpus, member(person_id=first), "B") is None


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load(PACK)


@pytest.fixture(scope="module")
def oracle() -> Oracle:
    return load_oracle(PACK)


@pytest.mark.parametrize("user_id", ["U-03", "U-04"])
def test_on_the_pack_every_step_is_a_relationship_the_scorer_calls_visible(
    corpus: Corpus, oracle: Oracle, user_id: str
) -> None:
    user, judged = corpus.users[user_id], oracle.users[user_id]
    paused = {p.person_id for p in access.rules().pauses}
    found = 0
    for record in access.candidates(corpus, user, (PERSON,), TODAY):
        path = graph.warm_path(corpus, user, record.id, TODAY)
        if path is None:
            continue
        found += 1
        assert path.people[0] == user.person_id and path.people[-1] == record.id
        assert 2 <= len(path.people) <= graph.MAX_STEPS + 1
        assert len(set(path.people)) == len(path.people)
        assert all(oracle.can_see(judged, p) for p in path.people)
        pairs = list(zip(path.people, path.people[1:], strict=False))
        for (a, b), used in zip(pairs, path.edges, strict=True):
            assert oracle.edge_ok(judged, a, b)
            assert {used.source, used.target} == {a, b}
            assert oracle.can_see(judged, used.id)
        assert not paused & set(path.people[1:-1])
    assert found > 0


@pytest.mark.parametrize("user_id", ["U-01", "U-02", "U-05"])
def test_on_the_pack_users_outside_the_network_get_no_path(corpus: Corpus, user_id: str) -> None:
    user = corpus.users[user_id]
    for record in access.candidates(corpus, user, (PERSON,), TODAY):
        assert graph.warm_path(corpus, user, record.id, TODAY) is None
