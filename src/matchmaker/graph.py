"""Warm paths: how the requester can be introduced to a person, through people they know.

A path is a chain of relationships from the requester to the match. Every relationship on
it must be one the requester may see (access policy, rule 2): the edge's own visibility is
at or below their clearance, and both people on it are visible to them. A relationship that
fails this is absent from the graph, so it can neither appear in a path nor shorten one.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from matchmaker import access
from matchmaker.corpus import PERSON, Corpus, Edge, User

# Beyond three introductions a path is no longer warm.
MAX_STEPS = 3


@dataclass(frozen=True)
class Path:
    people: tuple[str, ...]  # from the requester to the match, both included
    edges: tuple[Edge, ...]  # the relationship used for each step


def _clearance(user: User) -> int:
    return access.CLEARANCE.get(user.clearance, access.CLEARANCE["public"])


def _day(value: str) -> int:
    """A date as a number that grows with time; an unreadable date is the oldest."""
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return 0


def _stronger(edge: Edge) -> tuple[int, int, str]:
    """Sort key: the strongest relationship first, then the most recent, then by id."""
    return (-edge.strength, -_day(edge.last_interaction), edge.id)


def visible_edges(corpus: Corpus, user: User) -> list[Edge]:
    """Rule 2: the relationships this user may see."""
    clearance = _clearance(user)
    found: list[Edge] = []
    for edge in corpus.edges:
        if access.level(edge.visibility) > clearance:
            continue
        source, target = corpus.records.get(edge.source), corpus.records.get(edge.target)
        if source is None or target is None or source.kind != PERSON or target.kind != PERSON:
            continue
        if access.can_see(user, source) and access.can_see(user, target):
            found.append(edge)
    return found


def direct_edges(corpus: Corpus, user: User, person_id: str) -> list[Edge]:
    """The visible relationships between the requester and one person, strongest first."""
    if user.person_id is None:
        return []
    pair = {user.person_id, person_id}
    edges = [e for e in visible_edges(corpus, user) if {e.source, e.target} == pair]
    return sorted(edges, key=_stronger)


def _may_introduce(corpus: Corpus, user: User, person_id: str, today: date) -> bool:
    """Whether a person can stand in the middle of a path (rule 9)."""
    record = corpus.records[person_id]
    if access.pause_of(record, today) is not None:
        return False
    return not access.kept_apart(user, record)


def warm_path(corpus: Corpus, user: User, target_id: str, today: date | None = None) -> Path | None:
    """The shortest visible path from the requester to `target_id`, or None.

    Staff and guests have no place in the network (`person_id` is empty), so they get no
    path. Between paths of the same length, the one whose weakest relationship is strongest
    wins, then the stronger overall, then the more recent.
    """
    start = user.person_id
    target = corpus.records.get(target_id)
    if start is None or target is None or target.kind != PERSON or start == target_id:
        return None
    if start not in corpus.records:
        return None
    day = today or date.today()
    best: dict[frozenset[str], Edge] = {}
    for edge in sorted(visible_edges(corpus, user), key=_stronger):
        best.setdefault(frozenset((edge.source, edge.target)), edge)
    neighbours: defaultdict[str, list[str]] = defaultdict(list)
    for pair in best:
        if len(pair) == 2:
            a, b = sorted(pair)
            neighbours[a].append(b)
            neighbours[b].append(a)

    def paths_of(steps: int) -> list[tuple[str, ...]]:
        """Every path of exactly `steps` relationships, through people who may introduce."""
        found: list[tuple[str, ...]] = []

        def walk(trail: tuple[str, ...]) -> None:
            here = trail[-1]
            if len(trail) == steps:
                if target_id in neighbours[here]:
                    found.append((*trail, target_id))
                return
            for following in sorted(neighbours[here]):
                if following in trail or following == target_id:
                    continue
                if _may_introduce(corpus, user, following, day):
                    walk((*trail, following))

        walk((start,))
        return found

    paths: list[tuple[str, ...]] = []
    for steps in range(1, MAX_STEPS + 1):
        paths = paths_of(steps)
        if paths:
            break
    if not paths:
        return None

    def edges_of(people: tuple[str, ...]) -> tuple[Edge, ...]:
        return tuple(best[frozenset(step)] for step in zip(people, people[1:], strict=False))

    def quality(people: tuple[str, ...]) -> tuple[int, int, int, tuple[str, ...]]:
        edges = edges_of(people)
        return (
            -min(e.strength for e in edges),
            -sum(e.strength for e in edges),
            -min(_day(e.last_interaction) for e in edges),
            people,
        )

    chosen = min(paths, key=quality)
    return Path(chosen, edges_of(chosen))
