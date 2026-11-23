# Meridian matchmaking — one image, one command.
#
# Two stages, so the delivered image carries a virtualenv and the data pack and nothing else:
# no uv, no build context, no tests. Debian slim rather than Alpine because the wheels an LLM
# stack depends on (pydantic-core, tokenizers, numpy) are published for glibc; on musl they
# would be compiled from source at every build.
#
# The image carries configuration, never credentials. An API key is passed at run time
# (`docker run --env-file .env …`); `.env` is excluded from the build context, and CI fails
# the build if a credential-shaped variable ever lands in the image with a value.

FROM python:3.12-slim-bookworm AS builder

# Same uv version as CI (UV_VERSION in .github/workflows/ci.yml). Bump both together.
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first, in their own layer: a code change then rebuilds only the last step.
# --frozen: fail if uv.lock disagrees with pyproject.toml instead of silently re-resolving —
#   the image must contain exactly the versions the tests ran against.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --no-editable: install a real wheel. An editable install leaves a .pth pointing at
#   /app/src, which exists in this stage and not in the runtime one.
COPY src/ src/
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    MERIDIAN_PACK_DIR=/app/data/meridian_case_pack

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

# The case pack and its checksum manifest. Synthetic data, shipped in the image so that one
# `docker run` is enough; mount another directory and set MERIDIAN_PACK_DIR to replace it.
COPY data/ data/

# A fixed, high uid: not root, stable across rebuilds, and it will not collide with a host
# user if a results directory is mounted.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin matchmaker \
    && chown -R matchmaker:matchmaker /app
USER matchmaker

ENTRYPOINT ["matchmaker"]
CMD ["check-pack"]
