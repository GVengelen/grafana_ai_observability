"""Sigil AI observability bootstrap.

Call setup(settings) once at application startup (before any generation
is recorded) and shutdown() once at shutdown.  Both are no-ops when
settings.sigil_enabled is False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

# Module-level singletons populated by setup().
sigil_client = None
_tp = None
_mp = None


def setup(settings: "Settings") -> None:
    """Initialise OTel providers and Sigil client.

    Order is mandatory per SDK contract:
      1. TracerProvider
      2. MeterProvider
      3. sigil_sdk.Client
    """
    global sigil_client, _tp, _mp  # noqa: PLW0603

    if not settings.sigil_enabled:
        return

    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from sigil_sdk import AuthConfig, Client, ClientConfig, GenerationExportConfig

    resource = Resource.create({"service.name": settings.otel_service_name})

    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tp)
    _tp = tp

    mp = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(mp)
    _mp = mp

    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()

    sigil_client = Client(
        ClientConfig(
            generation_export=GenerationExportConfig(
                protocol=settings.sigil_protocol if hasattr(settings, "sigil_protocol") else "http",
                endpoint=settings.sigil_endpoint,
                auth=AuthConfig(
                    mode="basic",
                    tenant_id=settings.sigil_auth_tenant_id,
                    basic_password=settings.sigil_auth_token,
                ),
            ),
        )
    )


def shutdown() -> None:
    """Flush and shut down Sigil then OTel providers in the correct order."""
    global sigil_client, _tp, _mp  # noqa: PLW0603

    if sigil_client is not None:
        sigil_client.shutdown()
        sigil_client = None

    if _tp is not None:
        _tp.shutdown()
        _tp = None

    if _mp is not None:
        _mp.shutdown()
        _mp = None
