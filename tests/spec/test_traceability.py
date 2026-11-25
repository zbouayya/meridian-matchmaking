"""docs/SPECS.md and the tests cannot drift apart.

A requirement that claims to be enforced must have a test; a test must enforce a requirement
that exists; and a requirement cannot gain a test without its row saying so.
"""

from __future__ import annotations

from tests.spec.registry import ENFORCED_MODES, MODES, SPEC_ID, load_specs, marked_spec_ids


def test_the_specs_file_is_well_formed() -> None:
    specs = load_specs()
    assert specs, "no spec rows found in docs/SPECS.md"
    ids = [spec.id for spec in specs]
    assert len(ids) == len(set(ids)), f"duplicate spec ids: {sorted(set(ids)) != sorted(ids)}"
    for spec in specs:
        assert SPEC_ID.fullmatch(spec.id)
        assert spec.requirement, f"{spec.id} has no requirement"
        assert spec.source, f"{spec.id} names no source: every spec quotes a document"
        assert spec.mode in MODES, f"{spec.id}: unknown mode {spec.mode!r}"


def test_every_enforced_spec_has_a_test() -> None:
    marked = marked_spec_ids()
    missing = [s.id for s in load_specs() if s.mode in ENFORCED_MODES and s.id not in marked]
    assert not missing, f"marked as enforced in docs/SPECS.md, but no test declares them: {missing}"


def test_every_test_names_a_spec_that_exists() -> None:
    known = {spec.id for spec in load_specs()}
    unknown = {i: tests for i, tests in marked_spec_ids().items() if i not in known}
    assert not unknown, f"tests declare spec ids that are not in docs/SPECS.md: {unknown}"


def test_a_spec_with_a_test_says_so() -> None:
    marked = marked_spec_ids()
    stale = [s.id for s in load_specs() if s.mode not in ENFORCED_MODES and s.id in marked]
    assert not stale, f"these now have a test: change their mode in docs/SPECS.md: {stale}"
