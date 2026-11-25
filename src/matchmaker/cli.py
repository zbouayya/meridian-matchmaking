"""Command-line entry point.

Four commands:

- `check-pack` — the container's default, and what CI uses to prove the image works offline,
  as a non-root user, on a read-only filesystem.
- `check-llm` — one small paid request to each configured model, to prove the credential
  and the model ids work and to see what a request costs and takes.
- `baseline` — answers a file of requests with keyword search only, behind the access
  filter. No model is called. It is the result every later component is compared with.
- `run` — the matchmaker: rule-based ranking, then evidence and warm paths looked up in
  code, then one model call that writes the explanations.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from matchmaker import __version__, settings
from matchmaker.pack import PackNotFoundError, check_pack, resolve_pack_dir

EXIT_OK = 0
EXIT_PACK_ALTERED = 1
EXIT_PACK_NOT_FOUND = 2
EXIT_LLM_UNAVAILABLE = 3

DEFAULT_BASELINE_OUT = Path("results") / "baseline_keyword.jsonl"
DEFAULT_RESULTS_OUT = Path("results") / "results.jsonl"


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

    check_llm = commands.add_parser(
        "check-llm",
        help="send one small paid request to each configured model and report latency and cost",
    )
    check_llm.add_argument(
        "--model",
        action="append",
        default=None,
        help="model id to check; repeatable (default: the strong and the weak model)",
    )
    check_llm.set_defaults(handler=_check_llm)

    baseline = commands.add_parser(
        "baseline",
        help="answer a file of requests with keyword search only: the baseline to beat",
    )
    baseline.add_argument("--pack", type=Path, default=None, help="pack directory")
    baseline.add_argument(
        "--queries",
        type=Path,
        default=None,
        help="requests, one JSON object per line (default: the pack's 10 public requests)",
    )
    baseline.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_BASELINE_OUT,
        help=f"where the result lines are written (default: {DEFAULT_BASELINE_OUT})",
    )
    baseline.add_argument(
        "--synonyms",
        action="store_true",
        help="widen the search with the taxonomy's labels and synonyms, in three languages",
    )
    baseline.add_argument(
        "--theme-boost",
        action="store_true",
        help="move up the results that share a theme with the request",
    )
    baseline.add_argument(
        "--tags",
        action="store_true",
        help="also search the theme tags as plain words (kept for comparison)",
    )
    baseline.set_defaults(handler=_baseline)

    run = commands.add_parser(
        "run",
        help="answer a file of requests: rule-based ranking, evidence, warm paths, explanations",
    )
    run.add_argument("--pack", type=Path, default=None, help="pack directory")
    run.add_argument(
        "--queries",
        type=Path,
        default=None,
        help="requests, one JSON object per line (default: the pack's 10 public requests)",
    )
    run.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"where the result lines are written (default: {DEFAULT_RESULTS_OUT})",
    )
    run.add_argument(
        "--retrieval",
        choices=("rules", "model"),
        default="rules",
        help="who selects the matches: the rule-based ranking, or a model shown the "
        "table of records the user may be offered (default: rules)",
    )
    run.add_argument(
        "--no-model",
        action="store_true",
        help="call no model: explanations are written by rule",
    )
    run.set_defaults(handler=_run)

    build_tables = commands.add_parser(
        "build-tables",
        help="write the pack's people, organisations, initiatives and notes as CSV tables",
    )
    build_tables.add_argument("--pack", type=Path, default=None, help="pack directory")
    build_tables.add_argument(
        "--out", type=Path, default=Path("data") / "tables", help="folder for the CSV files"
    )
    build_tables.set_defaults(handler=_build_tables)
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


def _baseline(args: argparse.Namespace) -> int:
    from matchmaker import baseline, ranking

    pack_dir = resolve_pack_dir(args.pack)
    queries = args.queries or pack_dir / "eval" / "queries_public.jsonl"
    for path in (pack_dir, queries):
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return EXIT_PACK_NOT_FOUND
    options = ranking.Options(tags=args.tags, synonyms=args.synonyms, theme_boost=args.theme_boost)
    lines = baseline.run(pack_dir, queries, args.out, options=options)
    answered = sum(1 for line in lines if line["results"])
    slowest = max((line["latency_ms"] for line in lines), default=0.0)
    print(f"requests {len(lines)} ({answered} with at least one match)")
    print(f"slowest  {slowest:.1f} ms")
    print(f"written  {args.out}")
    return EXIT_OK


def _build_tables(args: argparse.Namespace) -> int:
    from matchmaker import tables
    from matchmaker.corpus import load

    pack_dir = resolve_pack_dir(args.pack)
    if not pack_dir.exists():
        print(f"error: {pack_dir} not found", file=sys.stderr)
        return EXIT_PACK_NOT_FOUND
    for path in tables.write(load(pack_dir), args.out):
        print(f"written  {path}")
    return EXIT_OK


def _run(args: argparse.Namespace) -> int:
    # Imported here: the model SDK is a large import that the other commands do not need.
    import os
    import statistics

    from matchmaker import llm, pipeline, ranking, selection, taxonomy, tracing
    from matchmaker.corpus import Record
    from matchmaker.keyword import Match

    pack_dir = resolve_pack_dir(args.pack)
    queries = args.queries or pack_dir / "eval" / "queries_public.jsonl"
    for path in (pack_dir, queries):
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return EXIT_PACK_NOT_FOUND
    settings.load_env_file()
    by_model = args.retrieval == "model" and not args.no_model
    suffix = "_model" if by_model else ""
    out: Path = args.out or Path("results") / f"results{suffix}.jsonl"
    # Every run leaves a trace of its steps next to its results, unless told otherwise.
    # That file holds one run: the previous one is replaced, not appended to.
    if not os.environ.get(tracing.TRACE_FILE_ENV):
        trace_file = out.with_name(f"traces{suffix}.jsonl")
        trace_file.unlink(missing_ok=True)
        os.environ[tracing.TRACE_FILE_ENV] = str(trace_file)
    stats_out = out.with_name(f"run_stats{suffix}.jsonl")
    options = ranking.Options(synonyms=True, theme_boost=True)
    themes = taxonomy.load(pack_dir)

    def rank_all(query: str, records: Sequence[Record]) -> list[Match]:
        return ranking.rank(query, records, options, themes, limit=max(len(records), 1))

    provider = tracing.setup()
    try:
        client = None if args.no_model else llm.make_client()
        ranker: ranking.Ranker = ranking.make_ranker(options, themes)
        if by_model and client is not None:
            ranker = selection.ModelRanker(client, rank_all)
        answers = pipeline.run(
            pack_dir, queries, out, ranker=ranker, client=client, stats_out=stats_out
        )
    finally:
        tracing.shutdown(provider)

    stats = [a.stats for a in answers]
    latencies = sorted(s["latency_ms"] for s in stats)
    by_model = sum(s.get("explained_by_model", 0) for s in stats)
    results = sum(s.get("results", 0) for s in stats)
    cost = sum(s.get("cost_usd") or 0.0 for s in stats)
    retrievals = [s.get("retrieval", {}) for s in stats]
    cost += sum(r.get("cost_usd") or 0.0 for r in retrievals)
    chosen_by_model = sum(1 for r in retrievals if r.get("by") == "model")
    print(f"requests     {len(answers)}")
    by_rules = len(answers) - chosen_by_model
    print(f"retrieval    {chosen_by_model} chosen by the model, {by_rules} by rules")
    print(
        f"results      {results}, {by_model} explained by the model, {results - by_model} by rule"
    )
    if latencies:
        median, slowest = statistics.median(latencies), latencies[-1]
        print(f"latency      median {median:.0f} ms, slowest {slowest:.0f} ms")
    print(f"model cost   ${cost:.4f}")
    for reason in sorted({s["fallback_reason"] for s in stats if s.get("fallback_reason")}):
        print(f"fallback     {reason}")
    from matchmaker.corpus import load

    for record_id, found in sorted(load(pack_dir).hidden_text.items()):
        print(f"hidden text  removed from {record_id} ({', '.join(found)}): for a person to check")
    print(f"written      {out}, {stats_out}")
    return EXIT_OK


def _check_llm(args: argparse.Namespace) -> int:
    # Imported here, not at the top: the SDK is a large import, and the commands that never
    # call a model should not pay for it at start-up.
    import anthropic

    from matchmaker import llm, tracing

    settings.load_env_file()
    configured = settings.models()
    names: list[str] = args.model or [configured.strong, configured.weak]
    # Tracing is registered before the client exists, so the SDK's own span for each call
    # lands under ours. These are the first traced calls of the project.
    provider = tracing.setup()
    try:
        try:
            client = llm.make_client()
        except anthropic.AnthropicError as exc:
            print(f"error: no usable credential: {exc}", file=sys.stderr)
            print("set ANTHROPIC_API_KEY in the environment or in ./.env", file=sys.stderr)
            return EXIT_LLM_UNAVAILABLE
        with tracing.step("matchmaker.check_llm"):
            pings = [llm.ping(client, name) for name in names]
    finally:
        tracing.shutdown(provider)
    width = max(len(p.model) for p in pings)
    for p in pings:
        if not p.ok:
            print(f"{p.model:<{width}}  FAIL  {p.detail}", file=sys.stderr)
            continue
        # Six decimals: a request this small costs a few millionths of a dollar.
        cost = "price unknown" if p.cost_usd is None else f"${p.cost_usd:.6f}"
        print(
            f"{p.model:<{width}}  OK    {p.latency_ms:6.0f} ms   "
            f"{p.input_tokens} in / {p.output_tokens} out   {cost}"
        )
    if all(p.ok for p in pings):
        return EXIT_OK
    if any(p.detail in llm.CREDENTIAL_PROBLEMS for p in pings):
        print("hint: set ANTHROPIC_API_KEY in the environment or in ./.env", file=sys.stderr)
    return EXIT_LLM_UNAVAILABLE


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
