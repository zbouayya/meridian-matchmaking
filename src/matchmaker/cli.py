"""Command-line entry point.

One command exists at scaffold time: `check-pack`. It is what the container runs by default
and what CI uses to prove the image works offline, as a non-root user, on a read-only
filesystem. The matchmaking commands are added to this parser as they are built.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from matchmaker import __version__
from matchmaker.pack import PackNotFoundError, check_pack, resolve_pack_dir

EXIT_OK = 0
EXIT_PACK_ALTERED = 1
EXIT_PACK_NOT_FOUND = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matchmaker",
        description="Cross-network matchmaking agent for the Meridian Forum case.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check-pack",
        help="verify the data pack is byte-identical to the one that was received",
    )
    check.add_argument(
        "--pack",
        type=Path,
        default=None,
        help="pack directory (default: $MERIDIAN_PACK_DIR, then ./data/meridian_case_pack)",
    )
    check.set_defaults(handler=_check_pack)
    return parser


def _check_pack(args: argparse.Namespace) -> int:
    pack_dir = resolve_pack_dir(args.pack)
    try:
        result = check_pack(pack_dir)
    except PackNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_PACK_NOT_FOUND

    print(f"pack     {result.pack_dir}")
    print(f"files    {result.expected} in the manifest")
    for label, names in (
        ("missing", result.missing),
        ("modified", result.modified),
        ("unexpected", result.unexpected),
    ):
        for name in names:
            print(f"{label:<9}{name}", file=sys.stderr)
    if result.ok:
        print("OK       byte-identical to the pack as received")
        return EXIT_OK
    print("FAIL     the pack differs from the one that was received", file=sys.stderr)
    return EXIT_PACK_ALTERED


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
