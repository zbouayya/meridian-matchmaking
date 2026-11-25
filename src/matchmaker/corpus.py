"""Load the case pack into records that can be filtered and ranked.

Three kinds of record can answer a request: people, organisations and initiatives. Notes
and relationships are loaded too, but they are never answers: they are evidence and the
material warm paths are built from. Text found in a record is data: nothing here
interprets it.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from matchmaker import documents, sanitize
from matchmaker.documents import Document

PERSON = "person"
ORGANIZATION = "organization"
INITIATIVE = "initiative"
KINDS = (PERSON, ORGANIZATION, INITIATIVE)

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class Record:
    """One person, organisation or initiative.

    `fields` holds the descriptive values (name, title, country…) and `body` the free text.
    The fields that govern access (`visibility`, `opt_out`) are kept apart on purpose: they
    are never searched.
    """

    id: str
    kind: str
    name: str
    visibility: str
    org_id: str | None
    opt_out: bool
    themes: tuple[str, ...]
    fields: tuple[str, ...]
    body: str
    # Kept as separate values for evidence and explanations; all optional.
    title: str = ""
    org_name: str = ""
    country: str = ""
    regions: tuple[str, ...] = ()
    last_engaged: str = ""
    participants: tuple[str, ...] = ()  # initiatives: the people taking part
    lead_orgs: tuple[str, ...] = ()  # initiatives: the organisations leading it


@dataclass(frozen=True)
class Note:
    """A session or account note. Never an answer; evidence at or above its visibility."""

    id: str
    title: str
    date: str
    visibility: str
    participants: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class Edge:
    """One row of `relationships.csv`: two people, and how they know each other."""

    id: str
    source: str
    target: str
    type: str
    strength: int
    last_interaction: str
    visibility: str
    evidence_doc: str
    note: str


@dataclass(frozen=True)
class User:
    id: str
    clearance: str
    person_id: str | None
    org_id: str | None


@dataclass(frozen=True)
class Corpus:
    records: dict[str, Record]
    users: dict[str, User]
    notes: dict[str, Note] = field(default_factory=dict)
    edges: tuple[Edge, ...] = ()
    documents: dict[str, Document] = field(default_factory=dict)
    # Record id -> what the cleaning removed from its text, for a person to look at.
    hidden_text: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _strings(*values: Any) -> tuple[str, ...]:
    """Flatten strings and lists of strings, dropping anything empty."""
    out: list[str] = []
    for value in values:
        items = value if isinstance(value, list) else [value]
        out += [item for item in items if isinstance(item, str) and item]
    return tuple(out)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def read_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    """Split a pack `.md` file into its header (`key: <json value>` lines) and its text."""
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{path.name}: no front matter")
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(": ")
        if separator:
            meta[key.strip()] = json.loads(value)
    return meta, match.group(2).strip()


def _record(kind: str, meta: dict[str, Any], fields: tuple[str, ...], body: str) -> Record:
    # Text a reader cannot see is removed here, before anything is searched or sent on.
    fields = tuple(sanitize.clean(value).strip() for value in fields)
    body = sanitize.clean(body).strip()
    return Record(
        id=str(meta["id"]),
        kind=kind,
        name=str(meta.get("name", "")),
        # A record with no stated visibility is treated as the most closed level.
        visibility=str(meta.get("visibility", "restricted")),
        org_id=meta.get("org_id") if kind == PERSON else None,
        opt_out=bool(meta.get("opt_out_matchmaking", False)),
        themes=_strings(meta.get("themes")),
        fields=fields,
        body=body,
        title=_text(meta.get("title")),
        org_name=_text(meta.get("org_name")),
        country=_text(meta.get("country")),
        regions=_strings(meta.get("region"), meta.get("regions")),
        last_engaged=_text(meta.get("last_engaged")),
        participants=_strings(meta.get("participants")),
        lead_orgs=_strings(meta.get("lead_orgs")),
    )


def _strength(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _notes(pack_dir: Path) -> dict[str, Note]:
    notes: dict[str, Note] = {}
    for path in sorted((pack_dir / "notes").glob("*.md")):
        meta, body = read_front_matter(path)
        notes[meta["id"]] = Note(
            id=str(meta["id"]),
            title=_text(meta.get("title")),
            date=_text(meta.get("date")),
            visibility=str(meta.get("visibility", "restricted")),
            participants=_strings(meta.get("participants")),
            body=sanitize.clean(body).strip(),
        )
    return notes


def _edges(pack_dir: Path) -> tuple[Edge, ...]:
    path = pack_dir / "relationships.csv"
    if not path.is_file():
        return ()
    with path.open(encoding="utf-8", newline="") as file:
        return tuple(
            Edge(
                id=row["edge_id"],
                source=row["source"],
                target=row["target"],
                type=row["type"],
                strength=_strength(row.get("strength") or ""),
                last_interaction=row.get("last_interaction") or "",
                visibility=row.get("visibility") or "restricted",
                evidence_doc=row.get("evidence_doc") or "",
                note=sanitize.clean(row.get("note") or "").strip(),
            )
            for row in csv.DictReader(file)
        )


def load(pack_dir: Path) -> Corpus:
    records: dict[str, Record] = {}
    hidden: dict[str, tuple[str, ...]] = {}
    for path in sorted((pack_dir / "people").glob("*.md")):
        meta, body = read_front_matter(path)
        fields = _strings(
            meta.get("name"),
            meta.get("title"),
            meta.get("org_name"),
            meta.get("country"),
            meta.get("region"),
            meta.get("communities"),
        )
        records[meta["id"]] = _record(PERSON, meta, fields, body)
        if found := sanitize.findings(body):
            hidden[meta["id"]] = found
    for path in sorted((pack_dir / "initiatives").glob("*.md")):
        meta, body = read_front_matter(path)
        fields = _strings(meta.get("name"), meta.get("regions"))
        records[meta["id"]] = _record(INITIATIVE, meta, fields, body)
        if found := sanitize.findings(body):
            hidden[meta["id"]] = found
    organisations = json.loads((pack_dir / "organizations.json").read_text(encoding="utf-8"))
    for meta in organisations:
        fields = _strings(
            meta.get("name"), meta.get("type"), meta.get("country"), meta.get("region")
        )
        records[meta["id"]] = _record(ORGANIZATION, meta, fields, "")
    users = {
        u["user_id"]: User(u["user_id"], u["clearance"], u.get("person_id"), u.get("org_id"))
        for u in json.loads((pack_dir / "users.json").read_text(encoding="utf-8"))
    }
    return Corpus(
        records, users, _notes(pack_dir), _edges(pack_dir), documents.load(pack_dir), hidden
    )
