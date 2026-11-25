# Every target here is what CI runs, so "it passes locally" and "it passes in CI" are the
# same statement. See .github/workflows/ci.yml.
.PHONY: install lint format typecheck test specs check run baseline docker-build docker-run start stop ci

IMAGE ?= meridian-matchmaking:local

# On WSL, a checkout on a Windows drive makes every Python import slow (30 s to import the
# model SDK). The virtualenv then goes on the Linux filesystem; anywhere else, nothing changes.
ifneq (,$(findstring /mnt/,$(CURDIR)))
export UV_PROJECT_ENVIRONMENT ?= $(HOME)/.venvs/meridian-matchmaking
endif

install:
	uv sync

lint:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .

# Rewrites files: import order, formatting, the fixes ruff considers safe.
format:
	uv run --frozen ruff check --fix .
	uv run --frozen ruff format .

typecheck:
	uv run --frozen mypy

test:
	uv run --frozen pytest -q

# The requirements of docs/SPECS.md: runs their tests and prints the report, one line per spec.
specs:
	-uv run --frozen pytest tests/spec -q
	@cat build/spec-report.md

check: lint typecheck test

# The matchmaker on the 10 public requests, then the pack's own scorer on its output. Calls
# the model once per request (about half a cent for the 10); without a key it still answers,
# with explanations written by rule.
run:
	uv run --frozen matchmaker run
	uv run --frozen python -B data/meridian_case_pack/eval/score.py --results results/results.jsonl

# The rule-based rankings on the 10 public requests, each scored with the pack's own scorer:
# plain keyword search, then the same with the taxonomy's synonyms and the theme re-ranking.
baseline:
	uv run --frozen matchmaker baseline --out results/baseline_keyword.jsonl
	uv run --frozen python -B data/meridian_case_pack/eval/score.py --results results/baseline_keyword.jsonl
	uv run --frozen matchmaker baseline --synonyms --theme-boost --out results/baseline_rules.jsonl
	uv run --frozen python -B data/meridian_case_pack/eval/score.py --results results/baseline_rules.jsonl

docker-build:
	docker build -t $(IMAGE) .

# Same flags as CI: no network, read-only root filesystem.
docker-run: docker-build
	docker run --rm --network none --read-only $(IMAGE)

# One click: checks the machine, builds the image, starts Phoenix (the trace viewer, at
# http://localhost:6006), verifies the pack, and calls each model once if a key is set.
start:
	bash scripts/start.sh

stop:
	docker compose down

ci: check docker-run
