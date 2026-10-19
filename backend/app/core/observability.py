"""OpenTelemetry bootstrap.

Call setup(settings) once at application startup and shutdown() once at
shutdown. No-op when otel_enabled is False.

Initialisation order:
  1. TracerProvider
  2. MeterProvider
  3. httpx instrumentation
  4. Agent Observability client (needs the providers above)

Shutdown runs in reverse: the Agent Observability client first, then OTel.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

# Module-level singletons populated by setup().
_tp = None
_mp = None
_agento11y_client = None


def get_agento11y_client():
    """Return the Agent Observability client, or None when not configured."""
    return _agento11y_client


def setup(settings: "Settings") -> None:
    global _tp, _mp  # noqa: PLW0603

    if not settings.otel_enabled:
        return

    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.otel_service_name})

    tp = TracerProvider(resource=resource)
    mp_readers = []

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    mp_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))

    trace.set_tracer_provider(tp)
    _tp = tp

    mp = MeterProvider(resource=resource, metric_readers=mp_readers)
    metrics.set_meter_provider(mp)
    _mp = mp

    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()

    _setup_agento11y(settings)


def _setup_agento11y(settings: "Settings") -> None:
    """Create the generation-export client from canonical AGENTO11Y_* env vars."""
    global _agento11y_client  # noqa: PLW0603

    if not os.environ.get("AGENTO11Y_ENDPOINT"):
        return

    from agento11y import Client, ClientConfig, HooksConfig

    # Telemetry must never block app startup: bad/missing config disables it.
    try:
        _agento11y_client = Client(
            ClientConfig(
                hooks=HooksConfig(
                    enabled=settings.agento11y_guards_enabled,
                    phases=["preflight"],
                    timeout_seconds=settings.agento11y_guards_timeout_ms / 1000,
                    # True: guard outage lets the LLM call proceed (dev). False: strict, outage raises.
                    fail_open=settings.agento11y_guards_fail_open,
                )
            )
        )
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "Agent Observability disabled: invalid AGENTO11Y_* config "
            "(is AGENTO11Y_AUTH_TOKEN set?)",
            exc_info=True,
        )


def shutdown() -> None:
    """Flush and shut down the OTel providers."""
    global _tp, _mp, _agento11y_client  # noqa: PLW0603

    # Client first: it flushes generations and emits final OTel metrics.
    if _agento11y_client is not None:
        _agento11y_client.shutdown()
        _agento11y_client = None

    if _tp is not None:
        _tp.shutdown()
        _tp = None

    if _mp is not None:
        _mp.shutdown()
        _mp = None
