"""Observability bootstrap for Sigil AI and OpenLIT.

Call setup(settings) once at application startup and shutdown() once at
shutdown. Each layer is a no-op when its respective enabled flag is False.

Initialisation order when both layers are active:
  1. TracerProvider  (shared, with one exporter per layer)
  2. MeterProvider   (shared)
  3. sigil_sdk.Client
  4. openlit.init()  (uses the already-registered global providers)
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
    global sigil_client, _tp, _mp  # noqa: PLW0603

    needs_otel = settings.sigil_enabled or settings.openlit_enabled
    if not needs_otel:
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

    # --- Sigil layer ---
    if settings.sigil_enabled:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from sigil_sdk import AuthConfig, Client, ClientConfig, GenerationExportConfig

        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        mp_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))

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

    # --- OpenLIT layer ---
    # OpenLIT gets its own OTLP exporter added to the shared TracerProvider so
    # both layers receive all spans without overriding each other's global state.
    if settings.openlit_enabled:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        openlit_trace_exporter = OTLPSpanExporter(endpoint=f"{settings.openlit_otlp_endpoint}/v1/traces")
        tp.add_span_processor(BatchSpanProcessor(openlit_trace_exporter))

        openlit_metric_exporter = OTLPMetricExporter(endpoint=f"{settings.openlit_otlp_endpoint}/v1/metrics")
        mp_readers.append(PeriodicExportingMetricReader(openlit_metric_exporter))

    trace.set_tracer_provider(tp)
    _tp = tp

    mp = MeterProvider(resource=resource, metric_readers=mp_readers)
    metrics.set_meter_provider(mp)
    _mp = mp

    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()

    if settings.openlit_enabled:
        import openlit

        # No otlp_endpoint — the shared TracerProvider already has the OpenLIT
        # OTLP exporter registered above, so spans flow there automatically.
        openlit.init(
            service_name="pokemon-qa-api",
            environment="devtalks",
            application_name=settings.otel_service_name
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
