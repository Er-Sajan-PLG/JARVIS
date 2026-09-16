"""
Anthropic (Claude) model client for JARVIS.

Direct integration with Anthropic's API.
https://docs.anthropic.com/claude/reference/messages_post

Usage:
  Set ANTHROPIC_API_KEY in your environment or .env file.
  In config.yaml, set backend: "anthropic" and api_key: "env:ANTHROPIC_API_KEY"
"""

import json
from collections.abc import Callable

import requests
from requests.exceptions import RequestException

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)


class AnthropicClient(ModelClient):
    """Model client for Anthropic API (Claude models)."""

    BASE_URL = "https://api.anthropic.com/v1"

    def __init__(
        self,
        model: str,
        api_key: str,
        role: str = "general",
    ):
        self._model = model
        self._role = role

        if not api_key:
            raise ValueError(
                "Anthropic requires an API key.\n"
                "Set ANTHROPIC_API_KEY in your environment or .env file."
            )

        self._api_key = api_key
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert OpenAI-style messages to Anthropic format.

        Returns (system_prompt, anthropic_messages)
        """
        system_parts = []
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue

            if role == "system":
                system_parts.append(content)
                continue

            anthropic_role = "assistant" if role == "assistant" else "user"

            # Merge consecutive messages with same role
            if anthropic_messages and anthropic_messages[-1]["role"] == anthropic_role:
                anthropic_messages[-1]["content"] += f"\n\n{content}"
            else:
                anthropic_messages.append({"role": anthropic_role, "content": content})

        system = "\n\n".join(system_parts) if system_parts else None
        return system, anthropic_messages

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a response via Anthropic."""
        system, anthropic_messages = self._convert_messages(messages)

        payload = {
            "model": self._model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            payload["top_k"] = kwargs["top_k"]

        if not stream:
            return self._generate_sync(payload)
        return self._generate_stream(payload, on_token)

    def _generate_sync(self, payload: dict) -> ModelResponse:
        url = f"{self.BASE_URL}/messages"
        try:
            res = requests.post(url, json=payload, headers=self._headers, timeout=120)
            res.raise_for_status()
            data = res.json()
        except RequestException as exc:
            raise ModelConnectionError(
                f"Could not reach Anthropic (model '{self._model}').",
                cause=exc,
            ) from exc
        except ValueError as exc:
            raise ModelResponseError(
                f"Malformed response from Anthropic model '{self._model}'.",
                cause=exc,
            ) from exc

        if "error" in data:
            raise ModelResponseError(
                f"Anthropic API Error: {data['error'].get('message', data['error'])}"
            )

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        tokens_used = None
        if "usage" in data:
            tokens_used = data["usage"].get("input_tokens", 0) + data["usage"].get(
                "output_tokens", 0
            )

        return ModelResponse(
            content=content,
            model=self._model,
            tokens_used=tokens_used,
            finish_reason=data.get("stop_reason"),
        )

    def _generate_stream(
        self,
        payload: dict,
        on_token: Callable[[str], None] | None,
    ) -> ModelResponse:
        url = f"{self.BASE_URL}/messages"
        try:
            res = requests.post(url, json=payload, headers=self._headers, stream=True, timeout=120)
            res.raise_for_status()
        except RequestException as exc:
            raise ModelConnectionError(
                f"Could not reach Anthropic (model '{self._model}').",
                cause=exc,
            ) from exc

        full_content = ""
        tokens_used = None
        finish_reason = None

        try:
            for line in res.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if not line.startswith("data: "):
                    continue
                chunk_str = line[6:].strip()
                if not chunk_str or chunk_str == "[DONE]":
                    continue

                try:
                    chunk = json.loads(chunk_str)
                except json.JSONDecodeError as exc:
                    raise ModelResponseError(
                        f"Malformed stream chunk from Anthropic model '{self._model}'.",
                        cause=exc,
                    ) from exc

                if chunk.get("type") == "error":
                    raise ModelResponseError(
                        f"Anthropic API Error: {chunk['error'].get('message', chunk['error'])}"
                    )

                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta", {}).get("text", "")
                    full_content += delta
                    if on_token and delta:
                        on_token(delta)

                if chunk.get("type") == "message_stop":
                    finish_reason = chunk.get("stop_reason")

                if chunk.get("type") == "message_delta":
                    if "usage" in chunk:
                        tokens_used = chunk["usage"].get("output_tokens")
        except RequestException as exc:
            raise ModelConnectionError(
                f"Anthropic stream for model '{self._model}' dropped mid-response.",
                cause=exc,
            ) from exc

        if finish_reason is None:
            raise ModelConnectionError(
                f"Anthropic stream for model '{self._model}' ended before completion."
            )

        return ModelResponse(
            content=full_content,
            model=self._model,
            tokens_used=tokens_used,
            finish_reason=finish_reason,
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role
