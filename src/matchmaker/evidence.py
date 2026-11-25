"""Evidence for one match: which records support it, and the facts a model may be told.

Everything here is a lookup by id, done in code: the initiatives a person takes part in,
the sessions they attended, the relationship that leads to them. No model decides what to
look up.

Every item goes through the access filter for the user who asked. An item that fails is
absent — not masked, not counted. Free text is then cleaned of any sentence that names a
record this user cannot see, so that a visible record cannot carry a hidden name through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from matchmaker import access, documents, graph
from matchmaker.corpus import INITIATIVE, ORGANIZATION, PERSON, Corpus, Edge, Record, User

MAX_INITIATIVES = 3
MAX_NOTES = 2
MAX_DOCUMENTS = 2
# How much text a model is given: a cap on the tokens a request can cost.
MAX_BIO_CHARS = 700
MAX_ABOUT_CHARS = 300

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING = re.compile(r"^#.*$", re.MULTILINE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_HONORIFIC = re.compile(r"^(?:dr|prof|mr|mrs|ms|mme|sr|sra)\.?\s+", re.IGNORECASE)
_MIN_NAME_LENGTH = 6


@dataclass(frozen=True)
class Evidence:
    record: Record
    ids: tuple[str, ...]  # what the result line cites: P-, O-, I-, N-, E-, D- and M- ids
    warm_path: tuple[str, ...]  # person ids from the requester to the match; empty if none
    facts: dict[str, Any]  # what a model is told about this match, and nothing more


def _clearance(user: User) -> int:
    return access.CLEARANCE.get(user.clearance, access.CLEARANCE["public"])


def hidden_names(corpus: Corpus, user: User) -> tuple[str, ...]:
    """Names and titles of everything this user cannot see, lower-cased.

    A name that is also part of a visible name is left out: finding it in a text does not
    show that the hidden record was meant.
    """
    clearance = _clearance(user)
    visible: list[str] = []
    hidden: set[str] = set()

    def sort(label: str, seen: bool) -> None:
        variants = {label.casefold(), _HONORIFIC.sub("", label).casefold()}
        if seen:
            visible.extend(variants)
        else:
            hidden.update(v for v in variants if len(v) >= _MIN_NAME_LENGTH)

    for record in corpus.records.values():
        if record.name:
            sort(record.name, access.can_see(user, record))
    for note in corpus.notes.values():
        if note.title:
            sort(note.title, access.level(note.visibility) <= clearance)
    for document in corpus.documents.values():
        if document.title:
            sort(document.title, access.level(document.visibility) <= clearance)
    return tuple(sorted(n for n in hidden if not any(n in v for v in visible)))


def clean(text: str, hidden: tuple[str, ...], limit: int) -> str:
    """Text fit to hand to a model: no markup comment, no heading, no sentence naming a
    hidden record, and no longer than `limit`."""
    plain = _HEADING.sub("", _HTML_COMMENT.sub(" ", text))
    kept = [
        sentence.strip()
        for sentence in _SENTENCE.split(" ".join(plain.split()))
        if sentence.strip() and not any(name in sentence.casefold() for name in hidden)
    ]
    out = ""
    for sentence in kept:
        if out and len(out) + len(sentence) + 1 > limit:
            break
        out = f"{out} {sentence}".strip()
    return out[:limit]


def _relationship(edge: Edge) -> dict[str, Any]:
    return {
        "type": edge.type.replace("_", " "),
        "strength": edge.strength,
        "last_interaction": edge.last_interaction,
    }


def _initiatives(corpus: Corpus, user: User, record: Record) -> list[Record]:
    found = [
        r
        for _, r in sorted(corpus.records.items())
        if r.kind == INITIATIVE
        and access.can_see(user, r)
        and (
            (record.kind == PERSON and record.id in r.participants)
            or (record.kind == ORGANIZATION and record.id in r.lead_orgs)
        )
    ]
    return found[:MAX_INITIATIVES]


def gather(
    corpus: Corpus,
    user: User,
    record: Record,
    today: date | None = None,
    hidden: tuple[str, ...] | None = None,
) -> Evidence:
    """The evidence for `record`, as seen by `user`. `record` must be one they may be offered."""
    names = hidden_names(corpus, user) if hidden is None else hidden
    clearance = _clearance(user)
    ids: list[str] = [record.id]
    facts: dict[str, Any] = {"id": record.id, "kind": record.kind, "name": record.name}
    for key, value in (
        ("title", record.title),
        ("organisation", record.org_name),
        ("country", record.country),
        ("regions", list(record.regions)),
        ("themes", list(record.themes)),
        ("last_engaged_with_the_forum", record.last_engaged),
        ("profile", clean(record.body, names, MAX_BIO_CHARS)),
    ):
        # A field naming a hidden record (an organisation above the user's level) is left out.
        if value and not (isinstance(value, str) and any(n in value.casefold() for n in names)):
            facts[key] = value

    initiatives = _initiatives(corpus, user, record)
    if initiatives:
        ids += [i.id for i in initiatives]
        facts["initiatives"] = [
            {"id": i.id, "name": i.name, "about": clean(i.body, names, MAX_ABOUT_CHARS)}
            for i in initiatives
        ]

    # Documents and emails that name the match, for a user whose clearance covers them.
    named_in = [
        (document, passages)
        for _, document in sorted(corpus.documents.items())
        if access.level(document.visibility) <= clearance
        and (passages := documents.passages_naming(document, record.name))
    ][:MAX_DOCUMENTS]
    if named_in:
        ids += [document.id for document, _ in named_in]
        facts["named_in"] = [
            {
                "id": document.id,
                "kind": document.kind,
                "title": document.title,
                "passage": clean(" ".join(passages), names, MAX_ABOUT_CHARS),
            }
            for document, passages in named_in
        ]

    path_people: tuple[str, ...] = ()
    if record.kind == PERSON:
        notes = [
            n
            for _, n in sorted(corpus.notes.items(), key=lambda item: item[1].date, reverse=True)
            if record.id in n.participants and access.level(n.visibility) <= clearance
        ][:MAX_NOTES]
        if notes:
            ids += [n.id for n in notes]
            facts["sessions_attended"] = [
                {
                    "id": n.id,
                    "title": n.title,
                    "date": n.date,
                    "about": clean(n.body, names, MAX_ABOUT_CHARS),
                }
                for n in notes
            ]
        path = graph.warm_path(corpus, user, record.id, today)
        if path is not None:
            path_people = path.people
            ids += [edge.id for edge in path.edges]
            facts["introduction_path"] = [
                {"from": corpus.records[a].name, "to": corpus.records[b].name} | _relationship(edge)
                for a, b, edge in zip(path.people, path.people[1:], path.edges, strict=False)
            ]
        direct = graph.direct_edges(corpus, user, record.id)
        if direct:
            facts["already_connected_to_the_requester"] = _relationship(direct[0])

    return Evidence(record, tuple(dict.fromkeys(ids)), path_people, facts)
