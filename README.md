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
- [ ] Matchmaking agent and access-policy tests
- [ ] `results.jsonl` on the 10 public requests, scorer output, baseline, latency report
- [ ] Assumptions, what was cut and what comes next
- [ ] Where AI coding assistants were used and what was checked by hand

## Run it

With Docker — nothing else to install:

```bash
docker build -t meridian-matchmaking . && docker run --rm meridian-matchmaking
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync && uv run matchmaker check-pack
```

Today the one command is `check-pack`: it verifies that the data pack in the repository (or
in the image) is byte-identical to the one that was received. The matchmaking command will
take its place as the default.

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
| Image build | Docker Buildx | The image builds from a clean checkout, from the lockfile |
| Image hygiene | shell assertions | Non-root user · no `.env` or key file · no credential-shaped variable with a value |
| Image run | `docker run --network none --read-only` | The container runs self-contained and the pack inside it is intact |

There is no deployment job, on purpose: this is a prototype, and CI stops at an image that
is proven to run.

## Layout

```
├── src/matchmaker/         the package (entry point: `matchmaker`)
├── tests/                  pytest suite, offline
├── data/
│   ├── meridian_case_pack/         the case pack, exactly as received
│   └── meridian_case_pack.sha256   SHA-256 of each of its 86 files
├── Dockerfile              two stages: uv builder → slim runtime, non-root
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

## Secrets

API keys live in a local `.env`, which is git-ignored and excluded from the Docker build
context. They are passed at run time (`docker run --env-file .env …`), never baked into the
image — CI fails the build if one is.

## Development

```bash
make install     # uv sync
make check       # lint + types + tests
make format      # apply ruff's fixes and formatting
make ci          # check, then build and run the image
```

`uvx pre-commit install` enables the same checks before each commit (optional).
