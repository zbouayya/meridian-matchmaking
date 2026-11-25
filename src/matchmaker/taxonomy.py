"""The pack's taxonomy, used two ways — both by rule, with no model.

- To recognise a theme in a request: one of the theme's labels (English, French, Spanish) or
  synonyms appears in it, word for word.
- To widen a search across languages: once a theme is recognised, the words of all its
  labels and synonyms are added to the search, so "hydrogène vert" also finds "green
  hydrogen" and "hidrógeno verde".

`taxonomy.json` itself is read, never edited.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from matchmaker.keyword import tokens


@dataclass(frozen=True)
class Theme:
    id: str
    phrases: tuple[tuple[str, ...], ...]  # each label or synonym, as words


Taxonomy = dict[str, Theme]


def load(pack_dir: Path) -> Taxonomy:
    raw = json.loads((pack_dir / "taxonomy.json").read_text(encoding="utf-8"))
    themes: Taxonomy = {}
    for theme_id, entry in raw.items():
        texts = [*entry.get("labels", {}).values(), *entry.get("synonyms", []), theme_id]
        phrases = {tuple(tokens(text)) for text in texts}
        themes[theme_id] = Theme(theme_id, tuple(sorted(p for p in phrases if p)))
    return themes


def _contains(words: list[str], phrase: tuple[str, ...]) -> bool:
    size = len(phrase)
    return any(tuple(words[i : i + size]) == phrase for i in range(len(words) - size + 1))


def themes_in(query: str, taxonomy: Taxonomy) -> tuple[str, ...]:
    """The themes a request names, in taxonomy order. Often none: that is a valid answer."""
    words = tokens(query)
    return tuple(
        theme.id for theme in taxonomy.values() if any(_contains(words, p) for p in theme.phrases)
    )


def related_words(theme_ids: tuple[str, ...], taxonomy: Taxonomy) -> tuple[str, ...]:
    """Every word of every label and synonym of these themes, without repeats."""
    words = [w for t in theme_ids for phrase in taxonomy[t].phrases for w in phrase]
    return tuple(dict.fromkeys(words))
