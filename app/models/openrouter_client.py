"""
OpenRouter model client for JARVIS.

OpenRouter provides access to 200+ cloud models through a single
OpenAI-compatible API. Useful for:
- Testing agent logic when local hardware is too weak
- Running tasks that need large context windows (1M tokens)
- Using stronger models for complex generation tasks

Usage:
  Set GOOGLE_API_KEY in your environment or .env file.
  In config.yaml, set backend: "openrouter" and api_key: "env:GOOGLE_API_KEY"

Recommended models:
  google/gemini-2.0-flash-001          — 1M context, cheap, reliable
  anthropic/claude-3-haiku-20240307    — best at XML/structured output
  mistralai/mistral-small-3.1-24b      — good balance
"""

import os
from typing import Callable, Optional

from openai import OpenAI

from app.models.client import ModelClient, ModelResponse


class OpenRouterClient(ModelClient):
    """
    Model client for OpenRouter cloud API.

    Architecturally identical to LlamaCppClient — same generate() signature,
    same ModelClient Protocol. The router can't tell the difference.
    Only difference: base_url points to OpenRouter, api_key is real.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

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
                "Set XAI_API_KEY in your environment or .env file."
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
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate a response via OpenRouter.

        stream and on_token are consumed here — NOT forwarded to the API.
        **kwargs (temperature, max_tokens, etc.) ARE forwarded.
        """
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
        for chunk in self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            **kwargs,
        ):
            delta = chunk.choices[0].delta.content or ""
            full_content += delta
            if on_token:
                on_token(delta)

        return ModelResponse(content=full_content, model=self._model)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role