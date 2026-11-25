"""Duplicate person records: the same person must never be offered twice.

The pack warns that it holds duplicates, like real CRM data. The rule here is deliberately
narrow: two person records are the same person when they belong to the same organisation
and the words of one name are all in the other ("Rafael Ortega" and "Rafael Ortega Ruiz").

The record engaged most recently is the one that is offered. The stale copy is not thrown
away: its text and themes are searched together with the kept record's, because the two
copies can describe the person in different languages.

It runs on the records a user may be offered, after the access filter, so a hidden record
can never change a visible one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from matchmaker.corpus import PERSON, Record
from matchmaker.keyword import tokens

_TITLES = frozenset({"dr", "prof", "mr", "mrs", "ms", "mme", "sr", "sra"})


def _name_words(record: Record) -> frozenset[str]:
    return frozenset(tokens(record.name)) - _TITLES


def same_person(a: Record, b: Record) -> bool:
    if a.kind != PERSON or b.kind != PERSON or not a.org_id or a.org_id != b.org_id:
        return False
    first, second = _name_words(a), _name_words(b)
    return bool(first and second) and (first <= second or second <= first)


def _merged(kept: Record, stale: Record) -> Record:
    return replace(
        kept,
        themes=tuple(dict.fromkeys(kept.themes + stale.themes)),
        fields=tuple(dict.fromkeys(kept.fields + stale.fields)),
        body=f"{kept.body}\n{stale.body}".strip(),
    )


def merge_duplicates(records: Sequence[Record]) -> list[Record]:
    """`records` with each duplicated person once, under the most recently engaged id."""
    merged = {record.id: record for record in records}
    for index, record in enumerate(records):
        for other in records[index + 1 :]:
            if record.id not in merged or other.id not in merged:
                continue
            if not same_person(record, other):
                continue
            # The more recently engaged record is kept; the first one on a tie.
            a, b = merged[record.id], merged[other.id]
            kept, stale = (b, a) if b.last_engaged > a.last_engaged else (a, b)
            merged[kept.id] = _merged(kept, stale)
            del merged[stale.id]
    return [merged[r.id] for r in records if r.id in merged]
