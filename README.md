# Meridian Forum — cross-network matchmaking

[![ci](https://github.com/zbouayya/meridian-matchmaking/actions/workflows/ci.yml/badge.svg)](https://github.com/zbouayya/meridian-matchmaking/actions/workflows/ci.yml)

Prototype of a matchmaking agent for the Meridian Forum take-home case: a natural-language
request from a known user goes in, up to five people, organisations or initiatives come out,
each with an explanation, its evidence and a warm introduction path — within that user's
access rights.

## Status

The engineering base is in place; the agent is built on top of it.

- [x] Reproducible environment (uv, locked), container image, CI on every push
- [x] Data pack committed byte for byte, with an integrity check
- [x] The case's explicit requirements written as specs, with tests waiting for the first output
- [x] Traces: every model call and step as an OpenTelemetry span, to a file and to a local viewer
- [x] Access filter, applied in code before anything is ranked, with its tests
- [x] Keyword baseline on the 10 public requests, scored with the pack's scorer (`make baseline`)
- [x] Matchmaker: rule-based ranking, evidence and warm paths looked up in code, explanations written by a model (`make run`)
- [x] `results/results.jsonl` on the 10 public requests, with the scorer output
- [x] Documents and emails read by the code, classified by what is written inside them, cited as evidence
- [x] Hidden text removed from records and requests; Secretariat rules in a structured file
- [ ] Region, recency and diversity in the ranking; latency report
- [ ] Assumptions, what was cut and what comes next
- [ ] Where AI coding assistants were used and what was checked by hand

## Deliverables

| Deliverable | Where | State |
|---|---|---|
| Business framing memo | [`docs/business-framing.md`](docs/business-framing.md) | First draft |
| Code and README | this repository | In progress |
| `results.jsonl` on the 10 public requests | [`results/results.jsonl`](results/results.jsonl) | Done, 25 November run |
| Evaluation and scale plan | [`docs/evaluation-and-scale.md`](docs/evaluation-and-scale.md) | Placeholder |

## Run it

With Docker Compose — the matchmaker, and Phoenix to look at its traces:

```bash
docker compose up --build
```

The traces are at <http://localhost:6006>. The viewer is optional: without it, or with it
stopped, every command gives the same results.

`bash scripts/start.sh` (or `make start`) does the same in one go and checks the machine
first: it builds the image, starts the viewer in the background, verifies the data pack and,
when an API key is set, calls each model once so a first trace is there to read. A first
run downloads about 400 MB; later runs take about half a minute.

With Docker alone, no viewer:

```bash
docker build -t meridian-matchmaking . && docker run --rm meridian-matchmaking
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync && uv run matchmaker check-pack
```

Today the default command is `check-pack`: it verifies that the data pack in the repository
(or in the image) is byte-identical to the one that was received. The matchmaking command
will take its place as the default.

The matchmaker answers the 10 public requests and is scored with the scorer that came with
the pack. It needs an API key for the explanations (see Models and secrets); without one it
still answers, with explanations written by rule:

```bash
make run
```

It writes `results/results.jsonl`, plus `run_stats.jsonl` (time, tokens and cost of each
request) and `traces.jsonl` (every step) beside it. For another file of requests:
`uv run matchmaker run --queries <file> --out <file>`.

The rule-based baselines — no model, no API key:

```bash
make baseline
```

That one writes `results/baseline_keyword.jsonl` (plain keyword search) and
`results/baseline_rules.jsonl` (the same, widened with the taxonomy's synonyms and re-ranked
by theme). Every request goes through the access filter (`src/matchmaker/access.py`) before
anything is searched. What we assumed along the way is in
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## Quality gates

Every push and pull request runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
`make ci` runs the same thing locally.

| Gate | Tool | What it proves |
|---|---|---|
| Lockfile | `uv lock --check` | `uv.lock` matches `pyproject.toml`; installs are `--frozen` everywhere |
| Lint | `ruff check` | Errors, likely bugs, import order, and the security rule set (bandit) |
| Format | `ruff format --check` | One style, no diff noise |
| Types | `mypy --strict` | Source and tests are fully typed |
| Tests | `pytest` | Offline by construction: no API key, no network |
| Specs | `pytest tests/spec` | The explicit requirements hold on the output; specs and tests cannot drift apart |
| Image build | Docker Buildx | The image builds from a clean checkout, from the lockfile |
| Image hygiene | shell assertions | Non-root user · no `.env` or key file · no credential-shaped variable with a value |
| Image run | `docker run --network none --read-only` | The container runs self-contained and the pack inside it is intact |
| Compose file | `docker compose config` | The viewer setup parses; the viewer itself is optional and is not started in CI |

There is no deployment job, on purpose: this is a prototype, and CI stops at an image that
is proven to run.

## Specs

[`docs/SPECS.md`](docs/SPECS.md) lists every requirement that is written down in the brief,
the access policy and the pack — 65 of them, each with its source and how it is enforced.
It also lists the points where the material is silent or contradicts itself.

- A test declares the specs it enforces with `@pytest.mark.spec("SEC-02", …)`. The suite
  fails if a spec marked as enforced has no test, or if a test names a spec that does not
  exist.
- The security, format, grounding and latency specs are checked on the system's output,
  `results/results.jsonl`, using the scorer shipped with the pack as the oracle. Until that
  file exists these tests are skipped and reported as waiting.
- Each check is first run against an output built to break it
  ([`tests/spec/test_checks_bite.py`](tests/spec/test_checks_bite.py)): a check that cannot
  fail is not a check.
- Every run writes `build/spec-report.md`, one line per spec, and CI publishes it in the job
  summary. `make specs` prints it locally.

## Layout

```
├── src/matchmaker/         the package (entry point: `matchmaker`)
├── docs/
│   ├── business-framing.md       the memo for the two client stakeholders
│   ├── evaluation-and-scale.md   scorer output, baseline, value metrics, scale plan
│   └── SPECS.md                  the case's explicit requirements, with ids
├── tests/                  pytest suite, offline
│   └── spec/               the specs as tests, and the report
├── data/
│   ├── meridian_case_pack/         the case pack, exactly as received
│   ├── secretariat_rules.json      introduction rules, written and approved by a person
│   └── meridian_case_pack.sha256   SHA-256 of each of its 86 files
├── Dockerfile              two stages: uv builder → slim runtime, non-root
├── compose.yaml            the image plus Phoenix, the trace viewer
├── scripts/start.sh        one command: checks, build, viewer, first traced call
├── Makefile                the CI steps as local targets
└── .github/workflows/      CI
```

## The data pack

`data/meridian_case_pack/` is never edited. The pack carries the evaluation labels and the
scorer next to the data, so a silent change — a line-ending conversion on checkout is
enough — would move the scores without touching a line of code. Three things guard it:

- `.gitattributes` stores the pack with `-text`: git never normalises a line ending in it.
- `data/meridian_case_pack.sha256` was generated once from the original zip.
  `matchmaker check-pack` and the test suite compare every file against it;
  `sha256sum -c` reads the same manifest.
- `ruff` and the pre-commit hooks exclude `data/`.

The pack's own README warns that it contains content that should not be trusted. Text found
in its records is treated as data, never as instructions.

## Models and secrets

The prototype calls the Claude API and compares two models: a strong one
(`claude-opus-5-5` by default) and a weak one (`claude-haiku-5-5`). Both can be changed with
`MATCHMAKER_STRONG_MODEL` and `MATCHMAKER_WEAK_MODEL`.

Copy `.env.example` to `.env` and add an API key, then check that both models answer:

```bash
uv run matchmaker check-llm
```

It sends one small request to each model and prints the latency, the tokens used and the
cost. `check-llm` and `run` are the only commands that spend money (about half a cent for
the 10 public requests), and the tests never do: they run against a fake client.

`.env` is git-ignored and excluded from the Docker build context. Keys are passed at run
time (`docker run --env-file .env …`), never baked into the image — CI fails the build if
one is. A variable already set in the environment wins over the file.

## Traces

Every model call and every step of the matchmaker is an OpenTelemetry span. The Claude SDK
emits the span for each API call itself — model, tokens, duration, status — and our own
steps are recorded around it.

| Destination | Switched on by | For |
|---|---|---|
| A JSON-lines file, one span per line | `MATCHMAKER_TRACE_FILE=results/traces.jsonl` | The record: what tests read |
| Phoenix, a local trace viewer | `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:6006` (set by `compose.yaml`) | Reading one request: steps, order, duration, tokens, cost |

- **The viewer can never cost a request.** Spans are sent from a background thread with a
  3-second timeout. With Phoenix stopped, a traced run ends normally with a warning.
- **Prompts stay out of traces by default.** The SDK records metadata only. `compose.yaml`
  turns content on because the pack is synthetic and the viewer is local; with real member
  data that line is the first to remove.
- **Phoenix is reduced to a viewer.** In `compose.yaml` its login is off and its port is
  bound to localhost; its usage telemetry, built-in assistant and MCP endpoint are
  disabled, and its version is pinned. Phoenix is under the Elastic License 2.0: free to
  run, not open source in the strict sense.

## Development

```bash
make install     # uv sync
make check       # lint + types + tests
make specs       # the spec tests, then the report: one line per requirement
make format      # apply ruff's fixes and formatting
make start       # one click: build, start the viewer, verify, first traced call
make stop        # stop the viewer (traces are kept)
make ci          # check, then build and run the image
```

On WSL with the checkout on a Windows drive, the `make` targets keep the virtualenv in
`~/.venvs/`: importing the model SDK takes 1.5 s there, against 30 s on the Windows drive.

`uvx pre-commit install` enables the same checks before each commit (optional).
