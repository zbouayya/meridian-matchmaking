"""Rule-based ranking: keyword search, and the two boosts that use the taxonomy.

Everything here is a rule — no model, nothing learned. Each option can be switched on alone,
so the evaluation can show what each one adds to plain keyword search.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from matchmaker import keyword, taxonomy
from matchmaker.corpus import Record
from matchmaker.keyword import Match

# A result sharing one theme with the request has its score raised by half; two themes
# double it. Set before looking at any score, and not tuned on the public requests.
THEME_BOOST = 0.5

Ranker = Callable[[str, Sequence[Record]], list[Match]]


@dataclass(frozen=True)
class Options:
    tags: bool = False  # search the theme tags as plain words
    synonyms: bool = False  # widen the search with the taxonomy's labels and synonyms
    theme_boost: bool = False  # move results that share a theme with the request up

    @property
    def uses_taxonomy(self) -> bool:
        return self.synonyms or self.theme_boost


def rank(
    query: str,
    records: Sequence[Record],
    options: Options | None = None,
    themes: taxonomy.Taxonomy | None = None,
    limit: int = 5,
) -> list[Match]:
    options = options or Options()
    named = taxonomy.themes_in(query, themes) if themes and options.uses_taxonomy else ()
    related = taxonomy.related_words(named, themes) if themes and options.synonyms else ()
    matches = keyword.rank(query, records, with_tags=options.tags, related=related, limit=None)
    if options.theme_boost and named:
        boosted = []
        for match in matches:
            shared = tuple(t for t in named if t in match.record.themes)
            score = match.score * (1 + THEME_BOOST * len(shared))
            boosted.append(replace(match, score=score, themes=shared))
        matches = sorted(boosted, key=lambda m: (-m.score, m.record.id))
    return matches[:limit]


def make_ranker(options: Options, themes: taxonomy.Taxonomy | None = None) -> Ranker:
    def ranker(query: str, records: Sequence[Record]) -> list[Match]:
        return rank(query, records, options, themes)

    return ranker


def describe(match: Match) -> str:
    """One sentence saying why a record matched, from the rules alone."""
    parts = []
    if match.terms:
        parts.append(f"shares these words with the request: {', '.join(match.terms)}")
    if match.related:
        parts.append(f"related words: {', '.join(match.related)}")
    if match.themes:
        parts.append(f"same theme: {', '.join(match.themes)}")
    sentence = "; ".join(parts) or "matches the request"
    return sentence[0].upper() + sentence[1:] + "."
