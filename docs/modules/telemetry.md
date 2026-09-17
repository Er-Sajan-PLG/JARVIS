# Telemetry

**Status**: ACTIVE
**Type**: reference
**Source**: `app/telemetry/` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Observability stack for JARVIS — distributed tracing (OpenTelemetry), metrics collection, and structured logging.

## Architecture

```
telemetry/
├── __init__.py
├── tracer.py (Tracer)
│   ├── start_span(name, attributes)
│   ├── end_span()
│   └── inject_context(carrier)
├── otel_exporter.py (OTLPExporter)
│   ├── export_spans(spans)
│   └── _otel_available() → bool
├── metrics.py (MetricsCollector)
│   ├── increment_counter(name, labels)
│   ├── record_histogram(name, value)
│   └── gauge(name, value)
└── logger.py (StructuredLogger)
    ├── info(message, **kwargs)
    ├── error(message, **kwargs)
    └── with_context(**kwargs)
```

## Components

### Tracer

In-memory span collector with optional OTLP export:
- Spans stored in ring buffer (max 10000)
- Export to Langfuse, Grafana Tempo, Honeycomb via OTLP
- Context propagation via W3C Trace Context

### OTLPExporter

Wraps `opentelemetry-sdk` for span export:
- Disabled by default (set `JARVIS_OTEL_ENABLED=true`)
- Endpoint: `JARVIS_OTEL_ENDPOINT` (default: `http://localhost:4317`)
- Service name: `JARVIS_OTEL_SERVICE_NAME` (default: `jarvis`)

### MetricsCollector

Prometheus-compatible metrics:
- Counters (requests_total, errors_total)
- Histograms (request_duration_seconds)
- Gauges (active_sessions)

### Logger

Structured JSON logging via `structlog`:
- Automatic trace ID injection
- Level-based filtering
- Output: stderr (configurable)

## Configuration

- `JARVIS_OTEL_ENABLED`: Enable OTLP export (default: `false`)
- `JARVIS_OTEL_ENDPOINT`: OTLP endpoint URL
- `JARVIS_METRICS_PORT`: Prometheus metrics port (default: `9090`)

## Semantic Conventions

```python
OTEL_AGENT_NAME = "gen_ai.agent.name"
OTEL_TOOL_NAME = "gen_ai.tool.name"
OTEL_GUARDRAIL_RESULT = "gen_ai.guardrail.result"
```

## API

```python
from app.telemetry import Tracer, MetricsCollector

tracer = Tracer()
with tracer.start_span("llm-call", {"provider": "openai"}):
    # ... LLM call ...

metrics = MetricsCollector()
metrics.increment_counter("requests_total", {"endpoint": "/chat"})
```
