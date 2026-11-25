"""The access policy, applied in code before anything is searched.

`candidates()` is the only door between the pack and a ranker: whatever ranks records — the
keyword baseline today, a model later — receives the records this user may be offered and
nothing else. A hidden record is not scored low; it is absent, so it cannot influence a
ranking, a count or an explanation.

Rule numbers refer to `data/meridian_case_pack/ACCESS_POLICY.md`.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from matchmaker.corpus import KINDS, PERSON, Corpus, Record, User
from matchmaker.pack import resolve_pack_dir

# Rule 1 — the clearance ladder.
CLEARANCE = {"public": 0, "members": 1, "staff": 2, "restricted": 3}
STAFF = CLEARANCE["staff"]
# Rule 8 — Secretariat staff are not recommended as experts.
SECRETARIAT_ORG = "O-20"


@dataclass(frozen=True)
class Pause:
    person_id: str
    until: date
    source: str


@dataclass(frozen=True)
class DoNotPair:
    people: frozenset[str]
    organisations: frozenset[str]  # the organisations those people belong to
    source: str


# Rule 9 — introduction rules the Secretariat recorded outside the structured fields. They
# live in a file beside the pack, written and approved by a person. No model writes it, and
# the reason for a rule is deliberately not in it.
RULES_FILE = "secretariat_rules.json"


@dataclass(frozen=True)
class Rules:
    pauses: tuple[Pause, ...]
    do_not_pair: tuple[DoNotPair, ...]


def load_rules(path: Path) -> Rules:
    """Read the rules file. A rule this code does not understand stops the run: applying
    only the rules that parse would silently lift the others."""
    pauses: list[Pause] = []
    pairs: list[DoNotPair] = []
    for rule in json.loads(path.read_text(encoding="utf-8"))["rules"]:
        source = ", ".join(rule["sources"])
        if rule["type"] == "pause":
            pauses.append(Pause(rule["person"], date.fromisoformat(rule["until"]), source))
        elif rule["type"] == "do_not_pair":
            pairs.append(
                DoNotPair(frozenset(rule["people"]), frozenset(rule["organisations"]), source)
            )
        else:
            raise ValueError(f"{path.name}: unknown rule type {rule['type']!r}")
    return Rules(tuple(pauses), tuple(pairs))


@cache
def rules() -> Rules:
    """The rules in force: the file that sits beside the pack."""
    return load_rules(resolve_pack_dir().with_name(RULES_FILE))


def level(name: str) -> int:
    """A visibility or clearance as a number. An unknown value is the most closed level."""
    return CLEARANCE.get(name, CLEARANCE["restricted"])


def can_see(user: User, record: Record) -> bool:
    """Rules 1 and 4: the ladder, and opted-out people hidden below staff."""
    clearance = CLEARANCE.get(user.clearance, CLEARANCE["public"])
    if level(record.visibility) > clearance:
        return False
    return not (record.kind == PERSON and record.opt_out and clearance < STAFF)


def is_staff(user: User) -> bool:
    return CLEARANCE.get(user.clearance, CLEARANCE["public"]) >= STAFF


def pause_of(record: Record, today: date) -> Pause | None:
    """The pause in force for this person on `today`, if there is one."""
    pauses = rules().pauses
    return next((p for p in pauses if p.person_id == record.id and today <= p.until), None)


def kept_apart(user: User, record: Record) -> bool:
    """Rule 9, do-not-pair: the requester and this record are on the two sides of a rule."""
    for rule in rules().do_not_pair:
        requester = user.person_id in rule.people or user.org_id in rule.organisations
        other = (
            record.id in rule.people
            or record.id in rule.organisations
            or record.org_id in rule.organisations
        )
        own = record.id in (user.person_id, user.org_id) or (
            record.org_id is not None and record.org_id == user.org_id
        )
        if requester and other and not own:
            return True
    return False


def may_suggest(user: User, record: Record, today: date) -> bool:
    """Rules 6, 8 and 9: a record the user may see can still be one not to offer."""
    if record.id in (user.person_id, user.org_id):
        return False
    if kept_apart(user, record):
        return False
    if record.kind != PERSON:
        return True
    if record.org_id is not None and record.org_id in (user.org_id, SECRETARIAT_ORG):
        return False
    # A paused person is never offered to a member or a guest. Staff still see them, with
    # the pause stated (see `flag`): they are the ones who can ask for it to be lifted.
    return is_staff(user) or pause_of(record, today) is None


def candidates(
    corpus: Corpus,
    user: User,
    kinds: Collection[str] = KINDS,
    today: date | None = None,
) -> list[Record]:
    """Every record this user may be offered, in id order."""
    day = today or date.today()
    return [
        record
        for _, record in sorted(corpus.records.items())
        if record.kind in kinds and can_see(user, record) and may_suggest(user, record, day)
    ]


def flags(user: User, record: Record, today: date | None = None) -> tuple[str, ...]:
    """What staff must be told about a person they are shown (rules 4 and 9).

    Members and guests are never told anything here: for them these people are absent.
    """
    if not is_staff(user) or not can_see(user, record):
        return ()
    found = []
    if record.opt_out:
        found.append("opted out of matchmaking")
    pause = pause_of(record, today or date.today())
    if pause is not None:
        until = f"{pause.until.day} {pause.until:%B %Y}"
        found.append(f"paused until {until}, ask before any introduction")
    return tuple(found)


def flag(user: User, record: Record, today: date | None = None) -> str:
    """The flags as one sentence, or an empty string."""
    found = flags(user, record, today)
    return f"Flag: {'; '.join(found)}." if found else ""
