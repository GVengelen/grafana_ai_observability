"""OpenTelemetry bootstrap.

Call setup(settings) once at application startup and shutdown() once at
shutdown. No-op when otel_enabled is False.

Initialisation order:
  1. TracerProvider
  2. MeterProvider
  3. httpx instrumentation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

# Module-level singletons populated by setup().
_tp = None
_mp = None


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


def shutdown() -> None:
    """Flush and shut down the OTel providers."""
    global _tp, _mp  # noqa: PLW0603

    if _tp is not None:
        _tp.shutdown()
        _tp = None

    if _mp is not None:
        _mp.shutdown()
        _mp = None
