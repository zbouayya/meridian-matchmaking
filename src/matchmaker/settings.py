"""Configuration read from the environment.

Secrets and model names come from environment variables. A `.env` file in the working
directory is a convenience for local runs; a variable that is already set always wins, so
`docker run --env-file`, a CI secret or an exported variable override the file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = ".env"

STRONG_MODEL_ENV = "MATCHMAKER_STRONG_MODEL"
WEAK_MODEL_ENV = "MATCHMAKER_WEAK_MODEL"
DEFAULT_STRONG_MODEL = "claude-opus-5-5"
DEFAULT_WEAK_MODEL = "claude-haiku-5-5"


@dataclass(frozen=True)
class Models:
    """The two models the case compares: where a strong one earns its cost, and where not."""

    strong: str
    weak: str


def load_env_file(directory: Path | None = None) -> bool:
    """Load `.env` from `directory` (default: the working directory), if there is one."""
    path = (directory or Path.cwd()) / ENV_FILE
    return path.is_file() and load_dotenv(path, override=False)


def models() -> Models:
    return Models(
        strong=os.environ.get(STRONG_MODEL_ENV) or DEFAULT_STRONG_MODEL,
        weak=os.environ.get(WEAK_MODEL_ENV) or DEFAULT_WEAK_MODEL,
    )
