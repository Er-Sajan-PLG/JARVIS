"""
Google Gemini model client for JARVIS.

Talks to the Google Generative Language API directly over HTTPS using
`requests` (already a project dependency). No manual source editing required:
select it in config.yaml with `backend: "google"`.

Unlike OpenAI-compatible backends, Gemini:
  - uses `user` / `model` roles (so OpenAI `assistant` -> `model`, and
    OpenAI `system` messages are lifted into Gemini's `systemInstruction`),
  - exposes a fixed REST endpoint (the model is selected via the URL path,
    not `base_url`), so `base_url` in config is ignored for Google models.

Usage:
  Set GOOGLE_API_KEY in your environment or .env file.
  In config.yaml, set backend: "google" and api_key: "env:GOOGLE_API_KEY"
"""

from typing import Callable, Optional

import requests
from requests.exceptions import RequestException

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)


class GoogleClient(ModelClient):
    """
    Model client for Google Gemini (Generative Language API).

    Implements the same `ModelClient` Protocol as `LlamaCppClient`,
    `OllamaClient`, and `OpenRouterClient` — `generate()`, `model_name`,
    and `role` — so the router/switcher treats it identically.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

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
                "Google Gemini requires an API key.\n"
                "Set GOOGLE_API_KEY in your environment or .env file,\n"
                "and reference it in config.yaml as api_key: \"env:GOOGLE_API_KEY\""
            )

        self._api_key = api_key

    # ---------------------------------------------------------------- #
    # Message / config helpers
    # ---------------------------------------------------------------- #
    def _split_messages(self, messages: list[dict]):
        """
        Convert OpenAI-style messages into Gemini's structure.

        Returns (system_instruction_text, contents) where:
          - all `system` roles are concatenated into one system instruction,
          - `assistant` -> `model`, `user` (and anything else) -> `user`,
          - consecutive messages with the same role are merged so Gemini's
            strict role-alternation rule is never violated.
        """
        system_parts: list[str] = []
        contents: list[dict] = []

        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if not text:
                continue

            if role == "system":
                system_parts.append(text)
                continue

            gemini_role = "model" if role == "assistant" else "user"
            if contents and contents[-1]["role"] == gemini_role:
                # Merge into previous turn (avoids same-role adjacency).
                contents[-1]["parts"].append({"text": text})
            else:
                contents.append({"role": gemini_role, "parts": [{"text": text}]})

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    @staticmethod
    def _build_generation_config(**kwargs) -> dict:
        """Map OpenAI-style kwargs to Gemini's `generationConfig`."""
        config: dict = {}
        if "temperature" in kwargs:
            config["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            config["maxOutputTokens"] = kwargs["max_tokens"]
        elif "maxOutputTokens" in kwargs:
            config["maxOutputTokens"] = kwargs["maxOutputTokens"]
        if "top_p" in kwargs:
            config["topP"] = kwargs["top_p"]
        if "top_k" in kwargs:
            config["topK"] = kwargs["top_k"]
        return config

    # ---------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------- #
    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate a response via Google Gemini.

        `stream` and `on_token` drive token-by-token streaming here (SSE).
        `**kwargs` (temperature, max_tokens, top_p, ...) are mapped to
        Gemini's `generationConfig`.
        """
        system_instruction, contents = self._split_messages(messages)
        payload: dict = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        generation_config = self._build_generation_config(**kwargs)
        if generation_config:
            payload["generationConfig"] = generation_config

        if not stream:
            return self._generate_sync(payload)
        return self._generate_stream(payload, on_token)

    # ---------------------------------------------------------------- #
    # Transport
    # ---------------------------------------------------------------- #
    def _generate_sync(self, payload: dict) -> ModelResponse:
        url = f"{self.BASE_URL}/models/{self._model}:generateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=120)
            res.raise_for_status()
            data = res.json()
        except RequestException as exc:
            raise ModelConnectionError(
                f"Could not reach Google Gemini (model '{self._model}').",
                cause=exc,
            ) from exc
        except ValueError as exc:  # json decode failure
            raise ModelResponseError(
                f"Malformed response from Google model '{self._model}'.",
                cause=exc,
            ) from exc

        if "error" in data:
            raise ModelResponseError(
                f"Google API Error: {data['error'].get('message', data['error'])}"
            )

        candidate = data["candidates"][0]
        text = self._extract_text(candidate)
        finish_reason = candidate.get("finishReason")
        tokens_used = (
            data.get("usageMetadata", {}).get("totalTokenCount")
            if data.get("usageMetadata") else None
        )
        return ModelResponse(
            content=text,
            model=self._model,
            tokens_used=tokens_used,
            finish_reason=finish_reason,
        )

    def _generate_stream(
        self,
        payload: dict,
        on_token: Optional[Callable[[str], None]],
    ) -> ModelResponse:
        url = (
            f"{self.BASE_URL}/models/{self._model}:streamGenerateContent"
            f"?alt=sse"
        )
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        try:
            res = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
            res.raise_for_status()
        except RequestException as exc:
            raise ModelConnectionError(
                f"Could not reach Google Gemini (model '{self._model}').",
                cause=exc,
            ) from exc

        full_content = ""
        tokens_used: Optional[int] = None
        finish_reason: Optional[str] = None

        try:
            for line in res.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if not line.startswith("data:"):
                    continue
                chunk_str = line[5:].strip()
                if not chunk_str or chunk_str == "[DONE]":
                    continue
                try:
                    chunk = _loads(chunk_str)
                except Exception as exc:
                    # A malformed chunk means we can't trust the stream —
                    # bail rather than returning a silently truncated or
                    # corrupted reply that could be persisted as history.
                    raise ModelResponseError(
                        f"Malformed stream chunk from Google model "
                        f"'{self._model}'.",
                        cause=exc,
                    ) from exc

                if "error" in chunk:
                    raise ModelResponseError(
                        f"Google API Error: "
                        f"{chunk['error'].get('message', chunk['error'])}"
                    )

                candidates = chunk.get("candidates")
                if candidates:
                    delta = self._extract_text(candidates[0])
                    full_content += delta
                    if on_token and delta:
                        on_token(delta)
                    finish_reason = candidates[0].get("finishReason") or finish_reason

                usage = chunk.get("usageMetadata")
                if usage and "totalTokenCount" in usage:
                    tokens_used = usage["totalTokenCount"]
        except RequestException as exc:
            # Mid-stream transport failure (network drop, truncated chunked
            # response, …): do NOT return the partial content we accumulated.
            raise ModelConnectionError(
                f"Google stream for model '{self._model}' dropped mid-response "
                f"(received {len(full_content)} chars).",
                cause=exc,
            ) from exc

        # The stream ended without an error but also without a finish reason,
        # which means it was cut off before completion (e.g. a network drop).
        # Refuse to return the partial content so it can't be persisted as a
        # valid assistant turn.
        if finish_reason is None:
            raise ModelConnectionError(
                f"Google stream for model '{self._model}' ended before "
                f"completion (received {len(full_content)} chars, no finish "
                f"reason)."
            )

        return ModelResponse(
            content=full_content,
            model=self._model,
            tokens_used=tokens_used,
            finish_reason=finish_reason,
        )

    # ---------------------------------------------------------------- #
    # Parsing
    # ---------------------------------------------------------------- #
    @staticmethod
    def _extract_text(candidate: dict) -> str:
        """Pull concatenated text out of a Gemini candidate."""
        parts = candidate.get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role


def _loads(s: str):
    """Local json import to avoid a top-level import in hot paths."""
    import json
    return json.loads(s)
