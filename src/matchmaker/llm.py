"""The model API: the client, what a call costs, and a connectivity check.

Nothing here does matchmaking. It answers three questions before any agent is written: is a
credential configured, do the two configured models answer, and what does a request cost
and take.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import anthropic

# USD per million tokens (input, output): Anthropic first-party API, standard speed, prompts
# under 100K tokens. Checked on 2026-11-03. A model missing from this table is reported with
# no cost rather than a guessed one.
PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-fable-5-2": (8.00, 40.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

PING_PROMPT = "Reply with the single word: ready"
PING_TIMEOUT_SECONDS = 30.0

NO_CREDENTIAL = "no credential configured"
CREDENTIAL_REJECTED = "the credential was rejected"
# The failures a key would fix. A timeout, a rate limit or an unknown model id is not one.
CREDENTIAL_PROBLEMS = frozenset({NO_CREDENTIAL, CREDENTIAL_REJECTED})


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """What a request cost, from its token usage. None when the model's price is unknown."""
    price = PRICES_USD_PER_MTOK.get(model)
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


def make_client() -> anthropic.Anthropic:
    """A client for diagnostics: it fails fast instead of retrying.

    Credentials are resolved by the SDK itself (ANTHROPIC_API_KEY first), never passed in.
    """
    return anthropic.Anthropic(timeout=PING_TIMEOUT_SECONDS, max_retries=0)


@dataclass(frozen=True)
class Ping:
    model: str
    ok: bool
    detail: str
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def ping(client: anthropic.Anthropic, model: str) -> Ping:
    """One small paid request to `model`: does it answer, how fast, at what cost.

    Sent without a refusal fallback on purpose: a fallback would let the check pass on a
    different model from the one being checked.
    """
    started = time.perf_counter()
    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": PING_PROMPT}],
        )
    except anthropic.AuthenticationError:
        return Ping(model, False, CREDENTIAL_REJECTED)
    except anthropic.PermissionDeniedError:
        return Ping(model, False, "this credential may not use this model")
    except anthropic.NotFoundError:
        return Ping(model, False, "unknown model id")
    except anthropic.RateLimitError:
        return Ping(model, False, "rate limited")
    except anthropic.APIStatusError as error:
        return Ping(model, False, f"API error {error.status_code}")
    except anthropic.APITimeoutError:
        return Ping(model, False, f"no answer within {PING_TIMEOUT_SECONDS:.0f} s")
    except anthropic.APIConnectionError:
        return Ping(model, False, "cannot reach the API")
    except anthropic.AnthropicError as error:
        return Ping(model, False, str(error).splitlines()[0] if str(error) else "client error")
    except TypeError as error:
        # With no credential at all, the SDK raises a bare TypeError while building the
        # request headers — not one of its own error classes. Anything else is a real bug.
        if "authentication" not in str(error):
            raise
        return Ping(model, False, NO_CREDENTIAL)

    latency_ms = (time.perf_counter() - started) * 1000
    usage = message.usage
    return Ping(
        model=model,
        ok=True,
        detail=f"answered ({message.stop_reason})",
        latency_ms=latency_ms,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=cost_usd(model, usage.input_tokens, usage.output_tokens),
    )
