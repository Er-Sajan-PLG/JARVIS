"""
OpenRouter model client for JARVIS.

OpenRouter provides access to 200+ cloud models through a single
OpenAI-compatible API. Useful for:
- Testing agent logic when local hardware is too weak
- Running tasks that need large context windows (1M tokens)
- Using stronger models for complex generation tasks

Usage:
  Set OPENROUTER_API_KEY in your environment or .env file.
  In config.yaml, set backend: "openrouter" and api_key: "env:OPENROUTER_API_KEY"

Recommended models:
  google/gemini-2.0-flash-001          — 1M context, cheap, reliable
  anthropic/claude-3-haiku-20240307    — best at XML/structured output
  mistralai/mistral-small-3.1-24b      — good balance
"""

from collections.abc import Callable

from openai import OpenAI, OpenAIError

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import (
    RESPONSE_SHAPE_ERRORS,
    ModelConnectionError,
    ModelResponseError,
    map_openai_error,
)


class OpenRouterClient(ModelClient):
    """
    Model client for OpenRouter cloud API.

    Architecturally identical to LlamaCppClient — same generate() signature,
    same ModelClient Protocol. The router can't tell the difference.
    Only difference: base_url points to OpenRouter, api_key is real.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    # Output ceiling sent when the caller does not specify one. Chat replies
    # are nowhere near this, and leaving it unset makes OpenRouter reserve the
    # model's full ceiling against the account balance (see generate()).
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        model: str,
        api_key: str,
        role: str = "general",
        site_url: str = "http://localhost",
        site_name: str = "JARVIS",
    ):
        self._model = model
        self._role = role

        if not api_key:
            raise ValueError(
                "OpenRouter requires an API key.\n"
                "Set OPENROUTER_API_KEY in your environment or .env file,\n"
                'and reference it in config.yaml as api_key: "env:OPENROUTER_API_KEY"'
            )

        self._client = OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
            default_headers={
                # OpenRouter identifies your app in their dashboard
                "HTTP-Referer": site_url,
                "X-Title": site_name,
            },
        )

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate a response via OpenRouter.

        stream and on_token are consumed here — NOT forwarded to the API.
        **kwargs (temperature, max_tokens, etc.) ARE forwarded.

        max_tokens defaults to DEFAULT_MAX_TOKENS when the caller omits it.
        This matters on pay-as-you-go accounts: with no max_tokens, OpenRouter
        assumes the model's full output ceiling (e.g. 65536) and pre-authorises
        the cost against the balance, so a large-ceiling model is rejected with
        HTTP 402 "request requires more credits, or fewer max_tokens" even
        though the actual reply would be tiny.
        """
        kwargs.setdefault("max_tokens", self.DEFAULT_MAX_TOKENS)

        try:
            if not stream:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    **kwargs,
                )
                return ModelResponse(
                    content=response.choices[0].message.content or "",
                    model=self._model,
                    tokens_used=response.usage.total_tokens if response.usage else None,
                    finish_reason=response.choices[0].finish_reason,
                )

            # Streaming path
            full_content = ""
            finish_reason = None
            for chunk in self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                **kwargs,
            ):
                # Servers may emit a trailing usage-only chunk with an
                # empty choices list; skip it rather than risking an
                # IndexError on choices[0].
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                full_content += delta
                if on_token:
                    on_token(delta)
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            # The stream ended without a terminating chunk (no finish_reason),
            # which means it was cut off before completion (e.g. a network
            # drop). Refuse to return the partial content so it can't be
            # persisted as a valid assistant turn.
            if finish_reason is None:
                raise ModelConnectionError(
                    f"Stream from model '{self._model}' ended before "
                    f"completion (received {len(full_content)} chars, no "
                    f"finish reason)."
                )
            return ModelResponse(
                content=full_content,
                model=self._model,
                finish_reason=finish_reason,
            )

        except OpenAIError as exc:
            # Connection errors, timeouts, rate limits, API/status errors →
            # a single typed ModelError rather than a raw openai exception.
            raise map_openai_error(exc, self._model) from exc
        except RESPONSE_SHAPE_ERRORS as exc:
            # Empty/odd payloads (no choices, missing fields) → clean error.
            raise ModelResponseError(
                f"Malformed response from model '{self._model}'.", cause=exc
            ) from exc

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role
