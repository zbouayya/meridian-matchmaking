#!/usr/bin/env bash
# One command: check the machine, build the image, start the trace viewer, prove it works.
#
#   bash scripts/start.sh        (or: make start)
#
# Safe to run again: everything already built or downloaded is reused. A first run downloads
# about 400 MB (the viewer image and the base images).
set -euo pipefail
cd "$(dirname "$0")/.."

VIEWER_URL="http://localhost:6006"

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

step "Checking this machine"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
docker info >/dev/null 2>&1 \
  || fail "Docker is installed but not running (on WSL: sudo service docker start)"
docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose is missing (on Ubuntu: sudo apt install docker-compose-v2)"
echo "docker $(docker version --format '{{.Server.Version}}'), compose $(docker compose version --short)"

# The key file: created from the example when missing, read by Docker Compose at run time,
# never copied into the image and never printed here.
if [ ! -f .env ]; then
  cp .env.example .env
  echo "created .env from .env.example"
fi
if grep -Eq '^ANTHROPIC_API_KEY=.+' .env; then has_key=yes; else has_key=no; fi

step "Building the image"
docker compose build --quiet matchmaker

step "Starting the trace viewer"
docker compose up --detach --wait --quiet-pull phoenix

step "Checking the data pack"
docker compose run --rm matchmaker check-pack

if [ "$has_key" = yes ]; then
  step "Calling each model once, traced"
  docker compose run --rm matchmaker check-llm \
    || echo "the model check failed: see the message above"
else
  step "Model check skipped"
  echo "no API key yet: put it after ANTHROPIC_API_KEY= in $(pwd)/.env and run this again"
fi

step "Ready"
echo "traces   $VIEWER_URL   (project: meridian-matchmaking)"
echo "run      docker compose run --rm matchmaker <command>"
echo "stop     docker compose down   (or: make stop)"
