"""
OmniModelClient — routes requests across multiple underlying ModelClient
instances to provide automatic failover and simple round-robin load
distribution across available cloud providers.

Behaviour:
- Tries clients in a round-robin order for each request.
- If a client raises a ModelError (connection, rate limit, timeout,
  response error), it is marked as failed and skipped for a short
  backoff window.
- For streaming calls we forward tokens from the chosen client; if the
  stream fails mid-way we attempt to complete the request with a
  subsequent client (non-streaming) and continue delivering tokens
  via the original `on_token` callback.

This wrapper implements the `ModelClient` protocol.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import ModelConnectionError, ModelError, ModelRateLimitError
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class OmniModelClient(ModelClient):
    def __init__(self, clients: list[ModelClient], backoff_seconds: int = 30):
        if not clients:
            raise ValueError("OmniModelClient requires at least one underlying client")
        self._clients = list(clients)
        self._idx = 0
        self._backoff = backoff_seconds
        # failed_until: idx -> unix timestamp when client can be retried
        self._failed_until: dict[int, float] = {}

    def _next_candidates(self):
        n = len(self._clients)
        start = self._idx % n
        for i in range(n):
            idx = (start + i) % n
            until = self._failed_until.get(idx, 0)
            if time.time() >= until:
                yield idx, self._clients[idx]

    def _mark_failed(self, idx: int, exc: ModelError):
        # Backoff on rate limits or connection failures; shorter backoff
        # for response errors.
        if isinstance(exc, (ModelRateLimitError, ModelConnectionError)):
            backoff = max(self._backoff, 5)
        else:
            backoff = min(self._backoff, 10)
        self._failed_until[idx] = time.time() + backoff

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        **kwargs,
    ) -> ModelResponse:
        last_exc: ModelError | None = None

        # Round-robin starting point advanced for the next call.
        start_idx = self._idx
        self._idx = (self._idx + 1) % len(self._clients)

        for idx, client in self._next_candidates():
            logger.info(
                "OmniModelClient: trying client %s (idx=%d)",
                getattr(client, "model_name", str(client)),
                idx,
            )
            try:
                if not stream:
                    return client.generate(messages, stream=False, **kwargs)

                # streaming path: prefer to stream from the chosen client
                # and forward tokens. If it fails mid-stream, try to get a
                # complete non-streaming response from a fallback client.
                try:
                    return client.generate(messages, stream=True, on_token=on_token, **kwargs)
                except ModelError as exc:
                    # mark failed and remember the exception
                    logger.warning(
                        "OmniModelClient: client %s failed during streaming: %s",
                        getattr(client, "model_name", str(client)),
                        exc,
                    )
                    self._mark_failed(idx, exc)
                    last_exc = exc
                    # continue to next client for non-streaming completion
                    continue

            except ModelError as exc:
                # For synchronous failures
                logger.warning(
                    "OmniModelClient: client %s failed: %s",
                    getattr(client, "model_name", str(client)),
                    exc,
                )
                self._mark_failed(idx, exc)
                last_exc = exc
                continue

        # If we reach here no client succeeded for the requested mode.
        if last_exc is not None:
            raise last_exc
        raise ModelError("No available model clients in OmniModelClient")

    @property
    def model_name(self) -> str:
        names = [c.model_name for c in self._clients]
        return "omni:" + ",".join(names)

    @property
    def role(self) -> str:
        # Return a comma-separated set of underlying roles (mostly same)
        roles = {c.role for c in self._clients}
        return ",".join(sorted(roles))
