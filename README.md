# Meridian Forum — cross-network matchmaking

[![ci](https://github.com/zbouayya/meridian-matchmaking/actions/workflows/ci.yml/badge.svg)](https://github.com/zbouayya/meridian-matchmaking/actions/workflows/ci.yml)

Prototype of a matchmaking agent for the Meridian Forum take-home case: a natural-language
request from a known user goes in, up to five people, organisations or initiatives come out,
each with an explanation, its evidence and a warm introduction path — within that user's
access rights.

## Deliverables

| Deliverable | Where |
|---|---|
| Business framing memo, two pages | [`docs/business-framing.md`](docs/business-framing.md) |
| Code and README | this repository |
| `results.jsonl` on the 10 public requests | [`results/results.jsonl`](results/results.jsonl) |
| Evaluation and scale plan | [`docs/evaluation-and-scale.md`](docs/evaluation-and-scale.md) |
| Architecture, as built and in production | [`docs/architecture.md`](docs/architecture.md) |
| Assumptions, open questions, improvement areas | [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) |

## Run it

You need [uv](https://docs.astral.sh/uv/): it installs the right Python and the locked
dependencies. Docker is only needed to look at the traces in a viewer.

```bash
uv sync
```

```bash
uv run matchmaker check-pack
```

```bash
make run
```

- `check-pack` verifies that the data pack in the repository is byte-identical to the one
  that was received.
- `make run` answers the 10 public requests, then scores them with the scorer that came
  with the pack. It writes `results/results.jsonl`, plus `run_stats.jsonl` (time, tokens
  and cost of each request) and `traces.jsonl` (every step) beside it.

Without `make`, the same run is two commands:

```bash
uv run matchmaker run
```

```bash
uv run python -B data/meridian_case_pack/eval/score.py --results results/results.jsonl
```

**With or without an API key.** With a key (see [Models and secrets](#models-and-secrets))
a model writes the explanations, for about half a cent for the 10 requests. Without one the
run still answers, with the same ranking and the same scores, and the explanations are
written by rule.

**Another file of requests,** for instance the hidden ones:

```bash
uv run matchmaker run --queries <requests.jsonl> --out results/hidden.jsonl
```

```bash
uv run python -B data/meridian_case_pack/eval/score.py --results results/hidden.jsonl --queries <requests.jsonl>
```

**With the traces in a viewer.** This is the only step that needs Docker:

```bash
make run-traced
```

It starts Phoenix, a local trace viewer, runs the same 10 requests and sends every step to
it. Open <http://localhost:6006>, project `meridian-matchmaking`: each request shows its
steps in order, with their duration, tokens and cost. `make stop` stops the viewer. Without
Docker only the viewer is lost: the same steps are in `results/traces.jsonl`.

**The tests,** offline and with no key:

```bash
uv run pytest -q
```

**What Docker is for here.** CI builds the image and runs it, to prove that the package
installs from the lockfile and runs offline as a non-root user (see
[CI and quality gates](#ci-and-quality-gates)). It is not the way to run the matchmaker:
use uv.

## Two retrieval modes

The matchmaker can choose its five matches in two ways. **Keywords are the default**, and
`results/results.jsonl` is produced that way.

| | Keywords (default) | Model |
|---|---|---|
| Command | `make run`, or `uv run matchmaker run` | `uv run matchmaker run --retrieval model` |
| Who chooses the five | Code: keyword search, widened with the taxonomy's synonyms in three languages, then re-ranked by theme | Claude Haiku, shown a table of the records this user may be offered |
| Model calls per request | 1, to write the explanations | 2: the selection, then the explanations |
| Same result on every run | Yes | No |
| nDCG@5 / P@5, 10 public requests | 0.893 / 0.980 | 0.929 / 0.960 (one run; an earlier one gave 0.906) |
| Median / slowest request | 2.0 s / 2.9 s | 2.6 s / 3.6 s |
| Model cost, 10 requests | $0.0048 | $0.0126 |
| Results file | `results/results.jsonl` | `results/results_model.jsonl` |

Both modes share everything else:

- **Before the selection, access:** the access filter (`src/matchmaker/access.py`) removes
  every record this user may not be offered. Neither the keyword search nor the model ever
  receives a hidden record.
- **Before the selection, two limits** (`src/matchmaker/limits.py`): a person the requester
  was in touch with in the last 90 days is not suggested, and no person is suggested more
  than twice in one run of requests. Both are filters in code, like the access filter.
- **After the selection:** evidence and warm introduction paths are looked up in code, one
  model call writes the explanations, and code checks every id before it is written.
- **When the model fails or is late:** the model mode falls back to the keyword ranking, and
  explanations fall back to sentences written by rule. A request always gets an answer.

Why keywords are the default:

- **The same request gives the same answer.** Three requests are re-run live at the debrief.
- **The selection takes about 3 ms.** The model's selection takes 0.6 to 1.1 s.
- **A sentence in a profile cannot move a rank.** In model mode the model reads every
  profile and decides the order.

The gap between the two scores, 0.013 on 10 requests, is too small to say that one mode
ranks better. The comparison is in
[`docs/evaluation-and-scale.md`](docs/evaluation-and-scale.md).

Other commands:

- `uv run matchmaker run --no-model` calls no model at all: keyword selection, explanations
  written by rule. No API key is needed, and it is what a run without a key does.
- `--recent-contact-days N` and `--max-suggestions N` change the two limits; 0 turns one
  off. Because of the second limit, requests are answered in the order of the file, and a
  request run alone can differ from the same request inside a run.
- `uv run matchmaker build-tables` writes the people, organisations, initiatives and notes
  as CSV tables in `data/tables/`. The model mode reads a reduced view of these tables:
  what a record is and does, never its visibility or opt-out.
- `make baseline` writes `results/baseline_keyword.jsonl` (plain keyword search) and
  `results/baseline_rules.jsonl` (keyword search with the taxonomy's synonyms and the theme
  re-ranking, before the two limits, with no model), and scores both.

What we assumed along the way is in [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## CI and quality gates

CI is GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). It runs on
every pull request and on every push to `main`, in two jobs:

- **`checks`** installs from the lockfile, then lints, type-checks and runs the test suite,
  the access-policy tests and the spec report included. About 30 seconds.
- **`image`** builds the Docker image from a clean checkout, checks that it holds no secret
  and runs as a non-root user, then runs it with no network and a read-only filesystem.
  About a minute.

What CI does not do:

- **It never calls a model.** The tests use a fake client, so no API key is stored in
  GitHub.
- **It deploys nothing.** This is a prototype: CI stops at an image that is proven to run.

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
│   ├── architecture.md           the pipeline as built and in production, two diagrams
│   ├── ASSUMPTIONS.md            assumptions, open questions, improvement areas
│   └── SPECS.md                  the case's explicit requirements, with ids
├── tests/                  pytest suite, offline
│   └── spec/               the specs as tests, and the report
├── data/
│   ├── meridian_case_pack/         the case pack, exactly as received
│   ├── secretariat_rules.json      introduction rules, written and approved by a person
│   ├── tables/                     people, organisations, initiatives and notes as CSV
│   └── meridian_case_pack.sha256   SHA-256 of each of its 86 files
├── Dockerfile              two stages: uv builder → slim runtime, non-root
├── compose.yaml            Phoenix, the trace viewer, and the image
├── scripts/start.sh        the Docker variant: build the image, start the viewer, check the pack
├── Makefile                the CI steps as local targets
└── .github/workflows/      CI
```

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
| Phoenix, a local trace viewer | `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:6006` (set by `make run-traced`) | Reading one request: steps, order, duration, tokens, cost |

- **The viewer can never cost a request.** Spans are sent from a background thread with a
  3-second timeout. With Phoenix stopped, a traced run ends normally with a warning.
- **Prompts stay out of traces by default.** The SDK records metadata only.
  `make run-traced` turns content on because the pack is synthetic and the viewer is
  local; with real member data that setting is the first to remove.
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
make run         # the 10 public requests, then the scorer
make run-traced  # the same, with every step sent to the trace viewer
make viewer      # start the trace viewer alone
make stop        # stop the viewer (traces are kept)
make ci          # check, then build and run the image
```

On WSL with the checkout on a Windows drive, the `make` targets keep the virtualenv in
`~/.venvs/`: importing the model SDK takes 1.5 s there, against 30 s on the Windows drive.

`uvx pre-commit install` enables the same checks before each commit (optional).
