"""Tests for the OTLP HTTP exporter."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.telemetry.otel_exporter import (
    OTLPExporter,
    _NoOpContextManager,
    create_otlp_exporter,
    is_otel_enabled,
)


class TestIsOtelEnabled:
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_otel_enabled() is False

    def test_enabled_when_env_true(self):
        with patch.dict(os.environ, {"JARVIS_OTEL_ENABLED": "true"}):
            assert is_otel_enabled() is True

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"JARVIS_OTEL_ENABLED": "TRUE"}):
            assert is_otel_enabled() is True

    def test_any_other_value_is_false(self):
        with patch.dict(os.environ, {"JARVIS_OTEL_ENABLED": "yes"}):
            assert is_otel_enabled() is False


class TestOTLPExporter:
    def test_init_with_defaults(self):
        """OTLPExporter initializes with default endpoint."""
        with patch.dict(os.environ, {}, clear=True):
            exporter = OTLPExporter()
            assert exporter.endpoint == "http://localhost:4317"
            assert exporter.service_name == "jarvis"

    def test_init_with_custom_endpoint(self):
        exporter = OTLPExporter(endpoint="http://custom:4317")
        assert exporter.endpoint == "http://custom:4317"

    def test_init_with_env_endpoint(self):
        with patch.dict(os.environ, {"JARVIS_OTEL_ENDPOINT": "http://env:4317"}):
            exporter = OTLPExporter()
            assert exporter.endpoint == "http://env:4317"

    def test_parse_headers(self):
        result = OTLPExporter._parse_headers("key1=val1,key2=val2")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_parse_headers_empty(self):
        assert OTLPExporter._parse_headers("") == {}

    def test_parse_headers_malformed(self):
        result = OTLPExporter._parse_headers("no_equals")
        assert result == {}

    def test_enabled_flag_reflects_sdk_availability(self):
        """If opentelemetry SDK is available, enabled should be True."""
        with patch("app.telemetry.otel_exporter._otel_available", return_value=True):
            exporter = OTLPExporter(endpoint="http://test:4317")
            # The actual enabled flag depends on whether the SDK can be fully initialized
            # In test env, it should be True since we have the SDK installed
            assert exporter.enabled is True

    def test_disabled_when_sdk_unavailable(self):
        """If opentelemetry SDK is not installed, enabled should be False."""
        with patch("app.telemetry.otel_exporter._otel_available", return_value=False):
            exporter = OTLPExporter(endpoint="http://test:4317")
            assert exporter.enabled is False

    def test_start_span_returns_noop_when_disabled(self):
        exporter = OTLPExporter(endpoint="")
        exporter._enabled = False
        ctx = exporter.start_span("test")
        assert isinstance(ctx, _NoOpContextManager)

    def test_start_span_context_manager_works(self):
        """The no-op context manager is a valid context manager."""
        ctx = _NoOpContextManager()
        with ctx:
            pass  # should not raise


class TestCreateOtelExporter:
    def test_returns_disabled_exporter_when_not_enabled(self):
        with patch.dict(os.environ, {}, clear=True):
            exporter = create_otlp_exporter()
            assert isinstance(exporter, OTLPExporter)

    def test_returns_exporter_when_enabled(self):
        with patch.dict(os.environ, {"JARVIS_OTEL_ENABLED": "true"}):
            exporter = create_otlp_exporter()
            assert isinstance(exporter, OTLPExporter)
