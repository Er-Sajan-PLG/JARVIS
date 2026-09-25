"""Tests for the append-only audit sink (Migration Plan Step 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.events import HITLRequestEvent, InMemoryAsyncBus, TokenUsageEvent
from app.security.audit_sink import AuditSink, audit_sink_enabled, maybe_attach_sink


def _read_records(sink_dir: Path) -> list[dict]:
    lines = []
    for path in sorted(sink_dir.glob("*.jsonl")):
        lines.extend(json.loads(line) for line in path.read_text().splitlines())
    return lines


async def test_token_usage_event_writes_jsonl_with_correlation_id(tmp_path: Path) -> None:
    sink = AuditSink(sink_dir=tmp_path)
    event = TokenUsageEvent(
        event_id="evt-1",
        event_type="token_usage",
        metadata={"correlation_id": "corr-123"},
        provider="openrouter",
        model="qwen/qwen3-coder:free",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost_usd=0.0,
    )

    await sink.on_event(event)

    (records) = _read_records(tmp_path)
    assert len(records) == 1
    (record) = records[0]
    assert record["correlation_id"] == "corr-123"
    assert record["event_type"] == "token_usage"
    assert record["actor"] == "llm"
    assert record["action"] == "token_usage"
    assert "timestamp" in record
    # Token *counts* are telemetry, not secrets — redaction must preserve them.
    assert record["details"]["total_tokens"] == 15
    assert record["details"]["prompt_tokens"] == 10


async def test_api_key_in_details_is_redacted(tmp_path: Path) -> None:
    sink = AuditSink(sink_dir=tmp_path)
    event = HITLRequestEvent(
        event_id="hitl-s1",
        event_type="hitl_request",
        plan_id="p1",
        step_id="s1",
        title="create dir",
        tool_name="create_directory",
        arguments={
            "path": "/tmp/x",
            "api_key": "sekret",
            "OPENROUTER_API_KEY": "sekret2",
            "content": "y" * 600,
        },
        description="create dir",
    )

    await sink.on_event(event)

    (record) = _read_records(tmp_path)[0]
    assert record["details"]["arguments"]["api_key"] == "[REDACTED]"
    assert record["details"]["arguments"]["OPENROUTER_API_KEY"] == "[REDACTED]"
    assert record["details"]["arguments"]["path"] == "/tmp/x"
    assert record["details"]["arguments"]["content"].endswith("...[truncated]")
    assert len(record["details"]["arguments"]["content"]) == 500 + len("...[truncated]")
    assert record["details"]["description"] == "create dir"


async def test_write_failure_does_not_propagate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = AuditSink(sink_dir=tmp_path)

    def _boom(record: dict, day: str) -> None:
        raise OSError("disk gone")

    monkeypatch.setattr(sink, "_write_line", _boom)
    event = TokenUsageEvent(event_id="evt-2", event_type="token_usage")

    await sink.on_event(event)  # must not raise

    assert list(tmp_path.glob("*.jsonl")) == []


def test_sink_disabled_via_env_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_AUDIT_SINK", "0")
    assert audit_sink_enabled() is False

    bus = InMemoryAsyncBus()
    assert maybe_attach_sink(bus) is None
    assert bus._handlers == {}
