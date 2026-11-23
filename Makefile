# Every target here is what CI runs, so "it passes locally" and "it passes in CI" are the
# same statement. See .github/workflows/ci.yml.
.PHONY: install lint format typecheck test check docker-build docker-run ci

IMAGE ?= meridian-matchmaking:local

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

check: lint typecheck test

docker-build:
	docker build -t $(IMAGE) .

# Same flags as CI: no network, read-only root filesystem.
docker-run: docker-build
	docker run --rm --network none --read-only $(IMAGE)

ci: check docker-run
