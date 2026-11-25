"""The model API layer, tested without the API: a fake client stands in for the SDK's.

No test here spends a token or opens a connection.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import anthropic
import httpx2
import pytest

from matchmaker import cli, llm, settings, tracing


@pytest.fixture(autouse=True)
def no_trace_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    """`check-llm` sets tracing up from the environment; here it must find nothing."""
    for name in (
        tracing.TRACE_FILE_ENV,
        tracing.OTLP_ENDPOINT_ENV,
        tracing.OTLP_TRACES_ENDPOINT_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


class FakeMessages:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return SimpleNamespace(
            model=request["model"],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=2_000, output_tokens=500),
        )


def fake_client(failure: Exception | None = None) -> tuple[anthropic.Anthropic, FakeMessages]:
    messages = FakeMessages(failure)
    return cast(anthropic.Anthropic, SimpleNamespace(messages=messages)), messages


def test_cost_follows_the_price_table() -> None:
    # 1M input + 1M output on the strong model: $4 + $20.
    assert llm.cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(24.00)
    assert llm.cost_usd("claude-haiku-5-5", 10_000, 3_000) == pytest.approx(0.0025)


def test_an_unknown_model_has_no_cost_rather_than_a_guess() -> None:
    assert llm.cost_usd("some-future-model", 1_000, 1_000) is None


def test_ping_reports_latency_tokens_and_cost() -> None:
    client, messages = fake_client()
    result = llm.ping(client, "claude-opus-5-5")
    assert result.ok
    assert (result.input_tokens, result.output_tokens) == (2_000, 500)
    assert result.cost_usd == pytest.approx(0.018)
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert messages.requests[0]["model"] == "claude-opus-5-5"
    assert messages.requests[0]["output_config"] == {"effort": "low"}


def test_ping_reports_an_unreachable_api_instead_of_raising() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client, _ = fake_client(anthropic.APIConnectionError(request=request))
    result = llm.ping(client, "claude-haiku-5-5")
    assert not result.ok
    assert result.detail == "cannot reach the API"
    assert result.cost_usd is None


def test_ping_reports_a_missing_credential_instead_of_a_traceback() -> None:
    # What the SDK raises when nothing is configured (seen in the container, which has no
    # credential profile on disk): a TypeError, not an anthropic error class.
    missing = TypeError('"Could not resolve authentication method. Expected one of api_key…"')
    client, _ = fake_client(missing)
    result = llm.ping(client, "claude-opus-5-5")
    assert not result.ok
    assert result.detail == "no credential configured"


def test_ping_does_not_swallow_an_unrelated_type_error() -> None:
    client, _ = fake_client(TypeError("unexpected keyword argument"))
    with pytest.raises(TypeError):
        llm.ping(client, "claude-opus-5-5")


def test_models_default_to_a_strong_and_a_weak_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(settings.STRONG_MODEL_ENV, raising=False)
    monkeypatch.delenv(settings.WEAK_MODEL_ENV, raising=False)
    assert settings.models() == settings.Models("claude-opus-5-5", "claude-haiku-5-5")
    monkeypatch.setenv(settings.WEAK_MODEL_ENV, "claude-sonnet-5-5")
    assert settings.models().weak == "claude-sonnet-5-5"


def test_the_env_file_never_overrides_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / settings.ENV_FILE).write_text(
        "MATCHMAKER_TEST_FROM_FILE=file\nMATCHMAKER_TEST_ALREADY_SET=file\n", encoding="utf-8"
    )
    monkeypatch.delenv("MATCHMAKER_TEST_FROM_FILE", raising=False)
    monkeypatch.setenv("MATCHMAKER_TEST_ALREADY_SET", "environment")
    assert settings.load_env_file(tmp_path)
    assert settings.load_env_file(tmp_path / "nowhere") is False

    import os

    assert os.environ["MATCHMAKER_TEST_FROM_FILE"] == "file"
    assert os.environ["MATCHMAKER_TEST_ALREADY_SET"] == "environment"
    monkeypatch.delenv("MATCHMAKER_TEST_FROM_FILE")


def test_check_llm_checks_both_models_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client, messages = fake_client()
    monkeypatch.setattr(settings, "load_env_file", lambda: False)
    monkeypatch.setattr(llm, "make_client", lambda: client)
    monkeypatch.delenv(settings.STRONG_MODEL_ENV, raising=False)
    monkeypatch.delenv(settings.WEAK_MODEL_ENV, raising=False)

    assert cli.main(["check-llm"]) == cli.EXIT_OK
    assert [r["model"] for r in messages.requests] == ["claude-opus-5-5", "claude-haiku-5-5"]
    out = capsys.readouterr().out
    assert "claude-opus-5-5" in out and "claude-haiku-5-5" in out and "$" in out


def test_check_llm_fails_when_a_model_does_not_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client, _ = fake_client(anthropic.APIConnectionError(request=request))
    monkeypatch.setattr(settings, "load_env_file", lambda: False)
    monkeypatch.setattr(llm, "make_client", lambda: client)

    assert cli.main(["check-llm", "--model", "claude-haiku-5-5"]) == cli.EXIT_LLM_UNAVAILABLE
    err = capsys.readouterr().err
    assert "cannot reach the API" in err
    # A key would not fix this, so the output must not send the reader to the key.
    assert "ANTHROPIC_API_KEY" not in err


def test_check_llm_points_at_the_key_when_the_key_is_the_problem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = TypeError('"Could not resolve authentication method. Expected one of api_key…"')
    client, _ = fake_client(missing)
    monkeypatch.setattr(settings, "load_env_file", lambda: False)
    monkeypatch.setattr(llm, "make_client", lambda: client)

    assert cli.main(["check-llm", "--model", "claude-haiku-5-5"]) == cli.EXIT_LLM_UNAVAILABLE
    err = capsys.readouterr().err
    assert llm.NO_CREDENTIAL in err
    assert "ANTHROPIC_API_KEY" in err
