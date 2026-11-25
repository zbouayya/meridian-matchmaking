"""Hidden text is removed before anything else runs.

Text that a person reading a profile cannot see has no business being searched or handed to
a model. It is removed when the pack is loaded and from every request: HTML comments,
elements hidden by their markup, scripts and styles, remaining tags, and characters that do
not display (zero-width and direction marks, tag characters, control codes).

This is hygiene, not a defence. An instruction written in plain sight goes straight
through. What makes a planted instruction harmless is elsewhere: the access filter runs
before any search, the ranking is done in code, and what the model writes is checked.
"""

from __future__ import annotations

import re
import unicodedata

_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_NOT_DISPLAYED = re.compile(r"<(script|style|template)\b.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_HIDDEN_BY_MARKUP = re.compile(
    r"<(\w+)\b[^>]*(?:\bhidden\b|display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0)"
    r"[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
# Format, control, private-use and surrogate characters: none of them displays.
_INVISIBLE_CATEGORIES = frozenset({"Cf", "Cc", "Co", "Cs"})
_KEPT_CONTROLS = frozenset("\n\t\r")


def _displays(char: str) -> bool:
    return char in _KEPT_CONTROLS or unicodedata.category(char) not in _INVISIBLE_CATEGORIES


def findings(text: str) -> tuple[str, ...]:
    """What `clean` would remove from `text`, in words — for a person to look at."""
    found = []
    visible = "".join(c for c in text if _displays(c))
    if visible != text:
        found.append("characters that do not display")
    if _COMMENT.search(visible):
        found.append("an HTML comment")
    if _HIDDEN_BY_MARKUP.search(visible) or _NOT_DISPLAYED.search(visible):
        found.append("an element that is not displayed")
    return tuple(found)


def clean(text: str) -> str:
    """`text` as a reader sees it. Invisible characters go first, so that they cannot be
    used to break up a marker and slip a comment past the next step."""
    out = "".join(c for c in text if _displays(c))
    for pattern in (_COMMENT, _NOT_DISPLAYED, _HIDDEN_BY_MARKUP):
        out = pattern.sub(" ", out)
    return _TAG.sub(" ", out)
