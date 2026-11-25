"""FUN-06 and SEC-11 — the documents and emails are read by the code, and classified by
what is written inside them. The scorer's own table of classifications is the oracle."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from matchmaker import documents
from tests.spec.conftest import PACK_DIR
from tests.spec.oracle import Oracle

FILES = ["D-01", "D-02", "D-03", "M-01", "M-02", "M-03"]


@pytest.mark.spec("FUN-06")
def test_every_pdf_word_and_email_file_is_parsed_into_passages() -> None:
    found = documents.load(PACK_DIR)
    assert sorted(found) == FILES
    assert {found[i].kind for i in FILES} == {"pdf", "word", "email"}
    assert all(found[i].passages for i in FILES)
    # A table row of the Word minutes stays one passage: who, with whom, and nothing else.
    assert any("P-027" in p and "P-050" in p for p in found["D-03"].passages)


@pytest.mark.spec("SEC-11")
@pytest.mark.parametrize("file_id", FILES)
def test_a_files_classification_is_the_one_written_inside_it(oracle: Oracle, file_id: str) -> None:
    assert documents.load(PACK_DIR)[file_id].visibility == oracle.kb[file_id]["visibility"]


@pytest.mark.spec("SEC-11")
def test_a_file_with_no_readable_classification_is_restricted(tmp_path: Path) -> None:
    unmarked = tmp_path / "M-09.eml"
    unmarked.write_text("From: A <a@x.example>\nSubject: Hello\n\nNo header.\n", encoding="utf-8")
    odd = tmp_path / "M-10.eml"
    odd.write_text(
        "From: A <a@x.example>\nSubject: Hello\nX-Meridian-Classification: everyone\n\nText.\n",
        encoding="utf-8",
    )
    broken = tmp_path / "D-09.pdf"
    broken.write_bytes(b"this is not a PDF")
    untitled = tmp_path / "D-10.docx"
    with zipfile.ZipFile(untitled, "w") as archive:
        archive.writestr("word/document.xml", "<w:p>Public-private partnerships, a review.</w:p>")
    for path in (unmarked, odd, broken, untitled):
        assert documents.read(path).visibility == "restricted"
    assert documents.read(broken).passages == ()
