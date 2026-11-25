"""Two limits on who is suggested, applied in code before anything is ranked.

They are not access rules: the user may see these people. They are suggestions the Forum
does not want to make, so the records are removed before the ranking, exactly as a hidden
record is. Neither the keyword search nor a model ever receives them.

- **Recent contact.** A person the requester was in touch with in the last
  `RECENT_CONTACT_DAYS` days is not suggested: the requester reaches them without the
  Forum. It reads the `last_interaction` date of the relationships between the two, and
  only relationships the requester may see.
- **Repetition.** A person already suggested `MAX_SUGGESTIONS` times since the ledger was
  opened is not suggested again, so that the same well-known names are not solicited again
  and again. In the prototype the ledger lives for one run of requests; in production it
  is the record of suggestions over a period.

Both apply to people only. A requester with no person record (staff, guests) has no
relationships of their own, so the first limit cannot act for them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from matchmaker import graph
from matchmaker.corpus import PERSON, Corpus, Record, User
from matchmaker.dedupe import same_person

# Both figures are working values, to be set with the relationship managers. 0 turns a
# limit off.
RECENT_CONTACT_DAYS = 90
MAX_SUGGESTIONS = 2


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def recent_contacts(
    corpus: Corpus, user: User, today: date, days: int = RECENT_CONTACT_DAYS
) -> dict[str, str]:
    """The people this requester was in touch with in the last `days` days.

    Person id -> date of the latest contact. Empty when the requester has no person record
    or when `days` is 0. A relationship whose date cannot be read is not counted.
    """
    if user.person_id is None or days <= 0:
        return {}
    cutoff = (today - timedelta(days=days)).isoformat()
    latest: dict[str, str] = {}
    for edge in graph.visible_edges(corpus, user):
        if user.person_id not in (edge.source, edge.target):
            continue
        other = edge.target if edge.source == user.person_id else edge.source
        when = edge.last_interaction
        if _is_date(when) and when >= cutoff and when > latest.get(other, ""):
            latest[other] = when
    return latest


@dataclass
class Ledger:
    """How many times each person has been suggested since the ledger was opened."""

    limit: int = MAX_SUGGESTIONS
    counts: Counter[str] = field(default_factory=Counter)

    def reached(self) -> frozenset[str]:
        """The people who may not be suggested again."""
        if self.limit <= 0:
            return frozenset()
        return frozenset(i for i, count in self.counts.items() if count >= self.limit)

    def record(self, suggested: Iterable[Record]) -> None:
        self.counts.update(r.id for r in suggested if r.kind == PERSON)


@dataclass(frozen=True)
class Applied:
    kept: list[Record]
    # The ids each limit left out, for the run's statistics. They are never shown to the
    # requester.
    recent_contact: tuple[str, ...] = ()
    repetition: tuple[str, ...] = ()


def _is_one_of(record: Record, others: Sequence[Record]) -> bool:
    """`record` is one of `others`, or another record of the same person."""
    return any(record.id == other.id or same_person(record, other) for other in others)


def apply(
    corpus: Corpus,
    user: User,
    records: Sequence[Record],
    today: date,
    ledger: Ledger | None = None,
    days: int = RECENT_CONTACT_DAYS,
) -> Applied:
    """`records` without the people either limit rules out.

    It runs before duplicate records are merged, so a limit reached under one record of a
    person also removes that person's other record.
    """
    contacts = [
        corpus.records[i] for i in recent_contacts(corpus, user, today, days) if i in corpus.records
    ]
    reached = ledger.reached() if ledger is not None else frozenset()
    repeated = [r for r in records if r.id in reached]
    kept: list[Record] = []
    recent_out: list[str] = []
    repeated_out: list[str] = []
    for record in records:
        if record.kind != PERSON:
            kept.append(record)
        elif _is_one_of(record, contacts):
            recent_out.append(record.id)
        elif _is_one_of(record, repeated):
            repeated_out.append(record.id)
        else:
            kept.append(record)
    return Applied(kept, tuple(recent_out), tuple(repeated_out))
