# app/telemetry

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Telemetry Package. | — |
| `correlation.py` | Request correlation context (Migration Plan Step 2.5). | — |
| `logger.py` | Telemetry & Event Logger. | `EventLogger` |
| `metrics.py` | Metrics Collector & Aggregator. | `AggregatedMetrics`, `MetricsCollector` |
| `otel_exporter.py` | OTLP HTTP exporter for JARVIS telemetry. | `OTLPExporter`, `_NoOpContextManager`, `_otel_available()`, `create_otlp_exporter()`, `is_otel_enabled()` |
| `trace_new.py` | Tracing helpers for the newer surfaces (Sprint 11.2). | `register_tracer()`, `traced()`, `traced_call()` |
| `tracer.py` | Operation Latency & Context Tracer. | `Tracer` |

<!-- generated:module_readmes end -->
