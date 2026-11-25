"""Traces, tested without a viewer and without the API.

The model API is replaced by a stub on the loopback interface, so the SDK emits the span it
would emit for a real call. Nothing here leaves the machine.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import anthropic
import pytest

from matchmaker import llm, tracing

STUB_REPLY = {
    "id": "msg_stub",
    "type": "message",
    "role": "assistant",
    "model": "claude-haiku-5-5",
    "content": [{"type": "text", "text": "ready"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 12, "output_tokens": 3},
}


class StubMessagesAPI(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", "0")))
        body = json.dumps(STUB_REPLY).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("request-id", "req_stub")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def stub_api() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), StubMessagesAPI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def read_spans(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def test_no_destination_means_no_tracing() -> None:
    assert tracing.build_provider({}) is None


def test_the_viewer_endpoint_follows_the_two_standard_variables() -> None:
    base = {tracing.OTLP_ENDPOINT_ENV: "http://phoenix:6006/"}
    assert tracing.otlp_traces_endpoint(base) == "http://phoenix:6006/v1/traces"
    full = {**base, tracing.OTLP_TRACES_ENDPOINT_ENV: "http://elsewhere:4318/custom"}
    assert tracing.otlp_traces_endpoint(full) == "http://elsewhere:4318/custom"
    assert tracing.otlp_traces_endpoint({}) is None


def test_spans_are_written_one_json_object_per_line(tmp_path: Path) -> None:
    trace_file = tmp_path / "results" / "traces.jsonl"
    provider = tracing.build_provider({tracing.TRACE_FILE_ENV: str(trace_file)})
    assert provider is not None
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("request") as request:
        request.set_attribute("matchmaker.query_id", "Q01")
        with tracer.start_as_current_span("search_network"):
            pass
    tracing.shutdown(provider)

    # A child ends before its parent, so it is written first.
    child, parent = read_spans(trace_file)
    assert (child["name"], parent["name"]) == ("search_network", "request")
    assert child["parent_id"] == parent["context"]["span_id"]
    assert child["context"]["trace_id"] == parent["context"]["trace_id"]
    assert parent["attributes"]["matchmaker.query_id"] == "Q01"
    assert parent["start_time"] <= child["start_time"] <= child["end_time"] <= parent["end_time"]
    assert parent["resource"]["attributes"]["service.name"] == tracing.SERVICE_NAME


def test_our_own_steps_are_labelled_for_the_viewer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_file = tmp_path / "traces.jsonl"
    provider = tracing.build_provider({tracing.TRACE_FILE_ENV: str(trace_file)})
    assert provider is not None
    test_tracer = provider.get_tracer("test")
    monkeypatch.setattr(tracing, "tracer", lambda: test_tracer)
    with tracing.step("matchmaker.check_llm"), tracing.step("search_network", kind="TOOL"):
        pass
    tracing.shutdown(provider)

    kinds = {s["name"]: s["attributes"][tracing.SPAN_KIND] for s in read_spans(trace_file)}
    assert kinds == {"matchmaker.check_llm": "CHAIN", "search_network": "TOOL"}


def test_an_unwritable_trace_file_is_skipped_not_fatal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    provider = tracing.build_provider({tracing.TRACE_FILE_ENV: str(blocker / "traces.jsonl")})
    assert provider is None
    assert "no trace file" in capsys.readouterr().err


def test_a_viewer_that_is_down_neither_fails_nor_stalls_a_run(tmp_path: Path) -> None:
    trace_file = tmp_path / "traces.jsonl"
    provider = tracing.build_provider(
        {
            tracing.TRACE_FILE_ENV: str(trace_file),
            tracing.OTLP_ENDPOINT_ENV: f"http://127.0.0.1:{closed_port()}",
        }
    )
    assert provider is not None
    started = time.perf_counter()
    with provider.get_tracer("test").start_as_current_span("request"):
        pass
    in_request = time.perf_counter() - started
    tracing.shutdown(provider)
    at_exit = time.perf_counter() - started

    assert [span["name"] for span in read_spans(trace_file)] == ["request"]
    assert in_request < 0.5, "the step itself must not wait for the viewer"
    assert at_exit < 2 * tracing.OTLP_TIMEOUT_SECONDS + 2, "the run must still end promptly"


def test_a_model_call_is_traced_by_the_sdk_without_its_prompt(
    tmp_path: Path, stub_api: str
) -> None:
    trace_file = tmp_path / "traces.jsonl"
    provider = tracing.build_provider({tracing.TRACE_FILE_ENV: str(trace_file)})
    assert provider is not None
    client = anthropic.Anthropic(
        api_key="not-a-real-key",
        base_url=stub_api,
        max_retries=0,
        open_telemetry={"tracer_provider": provider},
    )
    with provider.get_tracer("test").start_as_current_span("matchmaker.check_llm"):
        result = llm.ping(client, "claude-haiku-5-5")
    tracing.shutdown(provider)

    assert result.ok and (result.input_tokens, result.output_tokens) == (12, 3)
    spans = {span["name"]: span for span in read_spans(trace_file)}
    call, ours = spans["anthropic.messages.create"], spans["matchmaker.check_llm"]
    assert call["parent_id"] == ours["context"]["span_id"]
    assert call["attributes"]["gen_ai.request.model"] == "claude-haiku-5-5"
    assert call["attributes"]["gen_ai.usage.output_tokens"] == 3
    # Metadata only, by default: neither the prompt nor the answer is in the trace.
    written = trace_file.read_text(encoding="utf-8")
    assert llm.PING_PROMPT not in written
    assert "gen_ai.input.messages" not in written
    assert "gen_ai.output.messages" not in written


def test_account_identifiers_are_left_out_of_the_trace_file(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    provider = tracing.build_provider({tracing.TRACE_FILE_ENV: str(path)})
    assert provider is not None
    with provider.get_tracer("test").start_as_current_span("call") as span:
        span.set_attribute("anthropic.organization.id", "org-123")
        span.set_attribute("anthropic.workspace.id", "wrkspc-456")
        span.set_attribute("gen_ai.request.model", "claude-haiku-5-5")
    tracing.shutdown(provider)
    written = path.read_text(encoding="utf-8")
    assert "org-123" not in written and "wrkspc-456" not in written
    assert "claude-haiku-5-5" in written
