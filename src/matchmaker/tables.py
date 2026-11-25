"""The pack's records as tables: one row per record, with only the columns a reader needs.

Every person, initiative and note in the pack has the same shape — a header of fields, then
free text — so each kind becomes a table. Two uses:

- `write()` saves the full tables as CSV files, access fields included, for people to look
  at and maintain.
- `rows()` gives the view a model is shown when it selects matches: what a record is and
  does, and nothing about access. A model is never shown a visibility or an opt-out, and
  only ever receives rows the access filter has already let through.

The tables are built by code, not by a model: the fields are already structured in the pack.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from pathlib import Path

from matchmaker.corpus import INITIATIVE, ORGANIZATION, PERSON, Corpus, Record

# How much free text a row carries. It bounds what a selection costs and takes.
ABOUT_CHARS = 320
_HEADING = re.compile(r"^#.*$", re.MULTILINE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def about(text: str, limit: int = ABOUT_CHARS, hidden: Sequence[str] = ()) -> str:
    """The free text without its heading, cut at a sentence end below `limit`.

    `hidden` holds lower-cased names the reader may not see: a sentence that contains one
    is dropped whole. A public initiative can name a members-only participant.
    """
    plain = " ".join(_HEADING.sub("", text).split())
    out = ""
    for sentence in _SENTENCE.split(plain):
        if any(name in sentence.casefold() for name in hidden):
            continue
        if out and len(out) + len(sentence) + 1 > limit:
            break
        out = f"{out} {sentence}".strip()
    return out[:limit]


def row(record: Record, hidden: Sequence[str] = ()) -> dict[str, str]:
    """What a model is told about one candidate. Empty columns are left out."""
    columns = {
        "id": record.id,
        "kind": record.kind,
        "name": record.name,
        "title": record.title,
        "organisation": record.org_name,
        "country": record.country,
        "regions": ", ".join(record.regions),
        "themes": ", ".join(record.themes),
        "about": about(record.body, hidden=hidden),
    }
    # A field naming something the reader may not see (an organisation above their
    # level) is left out, like an empty one.
    return {
        key: value
        for key, value in columns.items()
        if value and not any(name in value.casefold() for name in hidden)
    }


def rows(records: Sequence[Record], hidden: Sequence[str] = ()) -> list[dict[str, str]]:
    return [row(record, hidden) for record in records]


def _write(path: Path, header: list[str], lines: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(lines)
    return path


def write(corpus: Corpus, out_dir: Path) -> list[Path]:
    """Save the full tables. These files hold every record: treat them like the pack."""

    def of(kind: str) -> list[Record]:
        return [r for _, r in sorted(corpus.records.items()) if r.kind == kind]

    def join(values: Sequence[str]) -> str:
        return "; ".join(values)

    people = [
        [
            r.id,
            r.name,
            r.title,
            r.org_id or "",
            r.org_name,
            r.country,
            join(r.regions),
            join(r.themes),
            r.last_engaged,
            r.visibility,
            str(r.opt_out).lower(),
            about(r.body, 2000),
        ]
        for r in of(PERSON)
    ]
    organisations = [
        [r.id, r.name, r.country, join(r.regions), join(r.themes), r.visibility]
        for r in of(ORGANIZATION)
    ]
    initiatives = [
        [
            r.id,
            r.name,
            join(r.themes),
            join(r.regions),
            join(r.lead_orgs),
            join(r.participants),
            r.visibility,
            about(r.body, 2000),
        ]
        for r in of(INITIATIVE)
    ]
    notes = [
        [n.id, n.title, n.date, join(n.participants), n.visibility, about(n.body, 2000)]
        for _, n in sorted(corpus.notes.items())
    ]
    return [
        _write(
            out_dir / "people.csv",
            [
                "id",
                "name",
                "title",
                "org_id",
                "organisation",
                "country",
                "regions",
                "themes",
                "last_engaged",
                "visibility",
                "opt_out",
                "about",
            ],
            people,
        ),
        _write(
            out_dir / "organisations.csv",
            ["id", "name", "country", "regions", "themes", "visibility"],
            organisations,
        ),
        _write(
            out_dir / "initiatives.csv",
            [
                "id",
                "name",
                "themes",
                "regions",
                "lead_orgs",
                "participants",
                "visibility",
                "about",
            ],
            initiatives,
        ),
        _write(
            out_dir / "notes.csv",
            ["id", "title", "date", "participants", "visibility", "about"],
            notes,
        ),
    ]
