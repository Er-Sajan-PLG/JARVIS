"""Tests for the Sprint 11.2 tracing helpers (no-op when no container)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.telemetry.trace_new import traced_call


class TestTraceNew:
    @pytest.mark.asyncio
    async def test_traced_call_no_container_noop(self):
        """Without a bootstrapped container, the call still runs, untraced."""
        called = AsyncMock(return_value="result")
        with patch(
            "app.bootstrap.bootstrap_system",
            side_effect=ImportError("no container"),
        ):
            out = await traced_call("comp", called)
        assert out == "result"

    @pytest.mark.asyncio
    async def test_traced_call_instruments(self):
        """With a container tracer, the call runs under a span."""
        container = MagicMock()
        tracer = MagicMock()
        span = AsyncMock()
        span.__aenter__ = AsyncMock(return_value=None)
        span.__aexit__ = AsyncMock(return_value=False)
        tracer.trace.return_value = span
        container.tracer = tracer
        called = AsyncMock(return_value="done")
        with patch("app.bootstrap.bootstrap_system", return_value=container):
            out = await traced_call("comp", called)
        assert out == "done"
        called.assert_awaited_once()
