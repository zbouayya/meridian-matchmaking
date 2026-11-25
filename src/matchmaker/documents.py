"""The pack's documents and emails: parsed, cut into passages, and classified.

These files are never answers. They are evidence: when one names a person, organisation or
initiative, it can be cited for that match — to a user whose clearance covers the file.

A file's classification is written inside it, not in a field (access policy, rule 10):

- an email carries it in its `X-Meridian-Classification` header;
- a PDF or Word file states it at the top, on a line that says "Classification:" or in a
  banner in capitals ("INTERNAL — STAFF ONLY").

Whatever cannot be read with certainty is treated as restricted. That includes a file that
does not parse at all.
"""

from __future__ import annotations

import email
import email.policy
import html
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from matchmaker import sanitize

LEVELS = ("public", "members", "staff", "restricted")
MOST_CLOSED = "restricted"
# How far down a document a classification is looked for.
BANNER_LINES = 5
_MIN_NAME_LENGTH = 6

_ID = re.compile(r"^([DM]-\d+)")
_LEVEL_WORD = re.compile(r"\b(public|members?|staff|restricted|confidential)\b", re.IGNORECASE)
_WORD_LEVEL = {
    "public": "public",
    "member": "members",
    "members": "members",
    "staff": "staff",
    "restricted": "restricted",
    "confidential": "restricted",
}
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_PAGE_FURNITURE = re.compile(r"^(?:page \d+|.*\bclassification\s*:.*)$", re.IGNORECASE)
_HONORIFIC = re.compile(r"^(?:dr|prof|mr|mrs|ms|mme|sr|sra)\.?\s+", re.IGNORECASE)
_TABLE_ROW = re.compile(r"<w:tr\b.*?</w:tr>", re.DOTALL)
_XML_TAG = re.compile(r"<[^>]+>")
_ADDRESS = re.compile(r"<[^>]*>")


@dataclass(frozen=True)
class Document:
    id: str
    kind: str  # "email", "word" or "pdf"
    title: str
    visibility: str
    passages: tuple[str, ...]


def _tidy(text: str) -> str:
    return " ".join(sanitize.clean(text).split())


def classification_of(lines: list[str]) -> str:
    """The level stated at the top of a document; restricted when none can be read.

    When a line names several levels, the most closed one is taken.
    """
    for line in lines[:BANNER_LINES]:
        lowered = line.casefold()
        banner = line.strip() != "" and line == line.upper() and any(c.isalpha() for c in line)
        if "classification" in lowered:
            stated = line[lowered.index("classification") + len("classification") :]
        elif banner:
            stated = line
        else:
            continue
        found = [_WORD_LEVEL[word.casefold()] for word in _LEVEL_WORD.findall(stated)]
        if found:
            return max(found, key=LEVELS.index)
        if "classification" in lowered:
            return MOST_CLOSED  # a classification line that cannot be read
    return MOST_CLOSED


def _email(path: Path) -> Document:
    message = email.message_from_string(
        path.read_text(encoding="utf-8"), policy=email.policy.default
    )
    stated = str(message.get("X-Meridian-Classification", "")).strip().casefold()
    visibility = stated if stated in LEVELS else MOST_CLOSED
    subject = _tidy(str(message.get("Subject", "")))
    # The sender's name without the address: the address is not needed to cite the email.
    sender = _tidy(_ADDRESS.sub("", str(message.get("From", ""))).strip(' "'))
    body = message.get_body(preferencelist=("plain",))
    text = body.get_content() if body is not None else ""
    paragraphs = [_tidy(p) for p in re.split(r"\n\s*\n", text)]
    opening = f"Email from {sender}: {subject}" if sender else subject
    passages = tuple(p for p in (opening, *paragraphs) if p)
    return Document(_id_of(path), "email", subject or path.stem, visibility, passages)


def _word(path: Path) -> Document:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    def row(match: re.Match[str]) -> str:
        cells = match.group(0).replace("</w:p>", " ").replace("</w:tc>", " | ")
        return cells + "\n"

    xml = _TABLE_ROW.sub(row, xml).replace("</w:p>", "\n")
    lines = [_tidy(html.unescape(_XML_TAG.sub("", line))) for line in xml.splitlines()]
    lines = [line.strip(" |") for line in lines if line.strip(" |")]
    return Document(_id_of(path), "word", _title_of(path), classification_of(lines), tuple(lines))


def _pdf(path: Path) -> Document:
    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    lines = [line.strip() for page in pages for line in page.splitlines() if line.strip()]
    text = " ".join(line for line in lines if not _PAGE_FURNITURE.match(line))
    passages = tuple(p for p in (_tidy(s) for s in _SENTENCE.split(text)) if p)
    return Document(_id_of(path), "pdf", _title_of(path), classification_of(lines), passages)


def _id_of(path: Path) -> str:
    match = _ID.match(path.stem)
    return match.group(1) if match else path.stem


def _title_of(path: Path) -> str:
    return _ID.sub("", path.stem).replace("_", " ").strip()


_READERS = {".eml": _email, ".docx": _word, ".pdf": _pdf}


def read(path: Path) -> Document:
    """One file as a document. A file that cannot be parsed is restricted and empty."""
    try:
        return _READERS[path.suffix.lower()](path)
    except Exception:  # whatever the parser raised, the answer is the same: closed
        return Document(_id_of(path), path.suffix.lstrip(".").lower(), path.stem, MOST_CLOSED, ())


def load(pack_dir: Path) -> dict[str, Document]:
    found: dict[str, Document] = {}
    for folder in ("documents", "inbox"):
        directory = pack_dir / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in _READERS:
                document = read(path)
                found[document.id] = document
    return found


def passages_naming(document: Document, name: str) -> list[str]:
    """The passages of `document` that name `name` in full (an honorific is ignored)."""
    wanted = _HONORIFIC.sub("", name).casefold().strip()
    if len(wanted) < _MIN_NAME_LENGTH:
        return []
    return [p for p in document.passages if wanted in p.casefold()]
