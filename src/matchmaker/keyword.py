"""Keyword search: the naive baseline.

A record scores on the words it shares with the request (BM25, the standard keyword-search
formula). No model and no translation: on its own, "hydrogène" does not match "hydrogen".
What is searched is the record's descriptive fields and its free text.

Two switches exist so that their effect can be measured, and both are off by default:

- `with_tags` also searches the theme tags as plain words ("green-hydrogen" gives "green"
  and "hydrogen"). Records that have no free text at all are always searched this way.
- `related` adds words the caller derived from the request — the taxonomy's labels and
  synonyms for a theme the request names. They count for less than the request's own words.

The word statistics are computed on the records passed in — the ones the user may see — so
a hidden record cannot move a score.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from matchmaker.corpus import Record

# BM25's two usual constants: how fast a repeated word stops counting, and how much a long
# record is penalised.
K1 = 1.2
B = 0.75
# A related word is worth half a word the requester actually wrote.
RELATED_WEIGHT = 0.5

_WORD = re.compile(r"[a-z0-9]+")
# Words that carry no topic, in the three languages of the pack.
_STOPWORD_LIST = """
    a an the of on in at to for and or who which with i me my our we is are be could would
    want also from by as that this it its their they them has have
    de des du la le les en un une pour et ou qui que dans sur avec au aux je nous est sont
    el los las para y o con por del al se su sus es son una uno
"""
STOPWORDS = frozenset(_STOPWORD_LIST.split())


def tokens(text: str) -> list[str]:
    """Lower-case words without accents, minus the stopwords and single characters."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return [w for w in _WORD.findall(plain) if len(w) > 1 and w not in STOPWORDS]


def searchable(record: Record, with_tags: bool = False) -> list[str]:
    parts = [*record.fields, record.body]
    # A record with no free text — every organisation in the pack — has nothing but its
    # theme tags to say what it does, so they are searched. Elsewhere they are a switch.
    if with_tags or not record.body.strip():
        parts += record.themes
    return tokens(" ".join(parts))


@dataclass(frozen=True)
class Match:
    record: Record
    score: float
    terms: tuple[str, ...]  # the request's words found in the record, in request order
    related: tuple[str, ...] = ()  # related words found in the record
    themes: tuple[str, ...] = ()  # themes shared with the request, when a boost used them


def rank(
    query: str,
    records: Sequence[Record],
    *,
    with_tags: bool = False,
    related: Sequence[str] = (),
    limit: int | None = 5,
) -> list[Match]:
    """The best records for `query`. A record sharing no word is never returned."""
    wanted = list(dict.fromkeys(tokens(query)))
    extra = [w for w in dict.fromkeys(related) if w not in wanted]
    documents = [Counter(searchable(record, with_tags)) for record in records]
    if not (wanted or extra) or not documents:
        return []
    average = sum(sum(d.values()) for d in documents) / len(documents) or 1.0
    containing = Counter(term for d in documents for term in d)

    def worth(term: str, counts: Counter[str], length: int) -> float:
        frequency = counts.get(term, 0)
        if not frequency:
            return 0.0
        n = containing[term]
        rarity = math.log(1 + (len(documents) - n + 0.5) / (n + 0.5))
        return rarity * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / average))

    matches: list[Match] = []
    for record, counts in zip(records, documents, strict=True):
        length = sum(counts.values())
        score = sum(worth(term, counts, length) for term in wanted)
        score += RELATED_WEIGHT * sum(worth(term, counts, length) for term in extra)
        if score > 0:
            matches.append(
                Match(
                    record,
                    score,
                    tuple(term for term in wanted if term in counts),
                    tuple(term for term in extra if term in counts),
                )
            )
    matches.sort(key=lambda m: (-m.score, m.record.id))
    return matches if limit is None else matches[:limit]
