"""Traces: every model call and every step of ours becomes an OpenTelemetry span.

Spans can go to two places, and each is switched on by its own variable:

- `MATCHMAKER_TRACE_FILE` — a JSON-lines file, one finished span per line. This is the
  record: tests and the latency report read it, and it needs nothing but a disk.
- `OTEL_EXPORTER_OTLP_ENDPOINT` — a trace viewer that speaks OTLP over HTTP. `compose.yaml`
  points it at Phoenix. The same spans, to look at.

Neither is allowed to cost a request. A file that cannot be opened is skipped with a
warning. The viewer is fed from a background thread with a short timeout, so a viewer that
is down slows nothing and fails nothing.

The Anthropic SDK emits its own span for each API call into the provider registered here.
It leaves prompts and responses out of spans unless
`ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE=content` is set; this module never sets it.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

TRACE_FILE_ENV = "MATCHMAKER_TRACE_FILE"
# The two standard OpenTelemetry variables. The first is a full URL, used as it is; the
# second is a base URL, to which the traces path is added.
OTLP_TRACES_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
OTLP_TRACES_PATH = "/v1/traces"
# How long one export to the viewer may take. Short on purpose: a viewer is a convenience.
OTLP_TIMEOUT_SECONDS = 3.0

SERVICE_NAME = "meridian-matchmaking"
TRACER_NAME = "matchmaker"
# The attribute Phoenix reads to label a span: CHAIN for a sequence of steps, TOOL,
# RETRIEVER… The SDK's model calls are recognised without it. An unlabelled span of ours
# shows as "unknown".
SPAN_KIND = "openinference.span.kind"


# Attributes the model SDK adds that identify the account the key belongs to. They are not
# credentials, but a trace file is meant to be shared, so they are left out of it.
ACCOUNT_ATTRIBUTES = frozenset({"anthropic.organization.id", "anthropic.workspace.id"})


class JsonLinesSpanExporter(SpanExporter):
    """Appends each finished span to a file as one JSON object per line."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file: TextIO = path.open("a", encoding="utf-8")
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            if self._file.closed:
                return SpanExportResult.FAILURE
            for span in spans:
                record = json.loads(span.to_json(indent=None))
                for name in ACCOUNT_ATTRIBUTES:
                    record.get("attributes", {}).pop(name, None)
                self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._file.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        with self._lock:
            self._file.close()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def otlp_traces_endpoint(env: Mapping[str, str]) -> str | None:
    """The URL spans are posted to, or None when no viewer is configured."""
    if full := env.get(OTLP_TRACES_ENDPOINT_ENV, "").strip():
        return full
    if base := env.get(OTLP_ENDPOINT_ENV, "").strip():
        return base.rstrip("/") + OTLP_TRACES_PATH
    return None


def build_provider(env: Mapping[str, str] | None = None) -> TracerProvider | None:
    """A tracer provider with the configured destinations, or None when there are none.

    Nothing is registered globally here, so tests can build as many as they need.
    """
    env = os.environ if env is None else env
    provider = TracerProvider(
        resource=Resource.create(
            # The second name is the one Phoenix files traces under.
            {"service.name": SERVICE_NAME, "openinference.project.name": SERVICE_NAME}
        ),
        # Shut down explicitly by the caller, so a run ends when its spans are written.
        shutdown_on_exit=False,
    )
    destinations = 0

    if trace_file := env.get(TRACE_FILE_ENV, "").strip():
        try:
            file_exporter = JsonLinesSpanExporter(Path(trace_file))
        except OSError as error:
            print(f"warning: no trace file, {trace_file}: {error}", file=sys.stderr)
        else:
            # Synchronous: a span is on disk when the step that produced it returns.
            provider.add_span_processor(SimpleSpanProcessor(file_exporter))
            destinations += 1

    if endpoint := otlp_traces_endpoint(env):
        # Imported here: it pulls in an HTTP stack that a run without a viewer never needs.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        otlp_exporter = OTLPSpanExporter(endpoint=endpoint, timeout=OTLP_TIMEOUT_SECONDS)
        # Batched on a background thread: the request never waits for the viewer.
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        destinations += 1

    return provider if destinations else None


def setup(env: Mapping[str, str] | None = None) -> TracerProvider | None:
    """Build the provider and register it for the whole process, the SDK's spans included."""
    provider = build_provider(env)
    if provider is not None:
        trace.set_tracer_provider(provider)
    return provider


def tracer() -> trace.Tracer:
    """The tracer for our own steps. Without a registered provider its spans are no-ops."""
    return trace.get_tracer(TRACER_NAME)


@contextmanager
def step(name: str, kind: str = "CHAIN") -> Iterator[trace.Span]:
    """One step of ours as a span, labelled so the viewer shows what kind of step it is."""
    with tracer().start_as_current_span(name, attributes={SPAN_KIND: kind}) as span:
        yield span


def shutdown(provider: TracerProvider | None) -> None:
    """Write out what is still buffered and close the destinations."""
    if provider is not None:
        provider.shutdown()
