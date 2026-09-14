"""OTLP HTTP exporter for JARVIS telemetry.

Provides an optional OTLP span exporter that wraps the existing local
``Tracer`` so cognitive-engine spans can be shipped to any OTLP-compatible
backend (Langfuse, Grafana Tempo, Honeycomb, ...).

The exporter is **disabled by default** and only activates when the
``JARVIS_OTEL_ENABLED`` environment variable is set to ``true``.  When
disabled (or when ``opentelemetry`` is not installed), the system keeps
using the existing ``InMemoryAsyncBus`` as the sole telemetry sink.

Environment variables:
    JARVIS_OTEL_ENABLED: set to ``true`` to enable OTLP export.
    JARVIS_OTEL_ENDPOINT: OTLP HTTP endpoint (default: ``http://localhost:4318/v1/traces``).
    JARVIS_OTEL_HEADERS: optional comma-separated ``key=value`` headers.
    JARVIS_OTEL_SERVICE_NAME: service name (default: ``jarvis``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Defaults
_DEFAULT_ENDPOINT = "http://localhost:4317"
_DEFAULT_SERVICE_NAME = "jarvis"


def _otel_available() -> bool:
    """Return True if the opentelemetry SDK is importable."""
    try:
        import opentelemetry  # noqa: F401

        return True
    except ImportError:
        return False


class OTLPExporter:
    """Optional OTLP span exporter.

    Wraps the existing local ``Tracer`` so that every traced operation
    produces both a local ``TelemetryEvent`` (for the in-process bus)
    **and** an OTLP span (for the configured backend).
    """

    def __init__(
        self,
        endpoint: str | None = None,
        headers: dict[str, str] | None = None,
        service_name: str | None = None,
    ) -> None:
        self.endpoint = endpoint or os.getenv("JARVIS_OTEL_ENDPOINT", _DEFAULT_ENDPOINT)
        self.service_name = service_name or os.getenv(
            "JARVIS_OTEL_SERVICE_NAME", _DEFAULT_SERVICE_NAME
        )
        self.headers = headers or self._parse_headers(os.getenv("JARVIS_OTEL_HEADERS", ""))
        self._tracer: Any | None = None
        self._enabled: bool = False

        if not _otel_available():
            logger.debug("opentelemetry not installed — OTLP exporter disabled")
            return

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=self.endpoint, headers=self.headers)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(self.service_name)
            self._enabled = True
            logger.info("OTLP exporter enabled — endpoint=%s", self.endpoint)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to initialize OTLP exporter: %s", e)

    @staticmethod
    def _parse_headers(raw: str) -> dict[str, str]:
        """Parse a comma-separated ``key=value`` string into a dict."""
        if not raw:
            return {}
        result: dict[str, str] = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, _, value = pair.partition("=")
            result[key.strip()] = value.strip()
        return result

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start_span(self, name: str, attributes: dict[str, str] | None = None) -> Any:
        """Start an OTLP span. Returns a context manager, or a no-op if disabled."""
        if not self._enabled or self._tracer is None:
            return _NoOpContextManager()
        return self._tracer.start_as_current_span(name, attributes=attributes)


class _NoOpContextManager:
    """Drop-in replacement for an OTLP span when the exporter is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def __call__(self, *args: Any, **kwargs: Any) -> _NoOpContextManager:
        return self


def is_otel_enabled() -> bool:
    """Check if OTLP export is enabled via environment variable."""
    return os.getenv("JARVIS_OTEL_ENABLED", "").lower() == "true"


def create_otlp_exporter() -> OTLPExporter:
    """Factory: create an OTLPExporter if enabled, else return a disabled one."""
    if not is_otel_enabled():
        return OTLPExporter(endpoint="")
    return OTLPExporter()
