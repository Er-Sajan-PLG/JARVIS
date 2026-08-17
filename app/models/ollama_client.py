# app/models/ollama_client.py
from typing import Optional, Callable
import ollama

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import (
    ModelResponseError,
    ModelConnectionError,
    RESPONSE_SHAPE_ERRORS,
    map_ollama_error,
    ollama_transport_errors,
)


class OllamaClient(ModelClient):
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        api_key: str = "not-needed",
        role: str = "general"
    ):
        self._model = model
        self._role = role

        if api_key and api_key.startswith("env:"):
            import os
            api_key = os.environ.get(api_key[4:].strip(), "not-needed")

        if not api_key:
            api_key = "not-needed"

        self._api_key = api_key

        # Ollama exposes an OpenAI-compatible API at <host>/v1; reuse the OpenAI
        # SDK (same pattern as LlamaCppClient) so generate()'s chat.completions
        # calls work against Ollama too.
        from openai import OpenAI
        self._client = OpenAI(base_url=base_url.rstrip("/") + "/v1", api_key=api_key)

    def generate(
        self, 
        messages: list[dict], 
        stream: bool = False, 
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse:
        try:
            if not stream:
                # --- STANDARD PATH ---
                response = self._client.chat.completions.create(
                    model=self._model, 
                    messages=messages, 
                    **kwargs
                )
                choice = response.choices[0]
                return ModelResponse(
                    content=choice.message.content,
                    model=self._model,
                    tokens_used=response.usage.total_tokens if response.usage else None,
                    finish_reason=choice.finish_reason,
                )
            
            # --- STREAMING PATH ---
            full_content = ""
            finish_reason = None
            stream_response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                **kwargs
            )

            for chunk in stream_response:
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

            # The stream ended without a terminating chunk (no
            # finish_reason), which means it was cut off before
            # completion (e.g. a network drop). Refuse to return the
            # partial content so it can't be persisted as a valid
            # assistant turn.
            if finish_reason is None:
                raise ModelConnectionError(
                    f"Stream from Ollama model '{self._model}' ended "
                    f"before completion (received {len(full_content)} "
                    f"chars, no finish reason)."
                )
            return ModelResponse(
                content=full_content,
                model=self._model,
                finish_reason=finish_reason,
            )

        except (ollama.ResponseError, *ollama_transport_errors()) as exc:
            # Network errors, timeouts, and Ollama HTTP errors → typed ModelError.
            raise map_ollama_error(exc, self._model) from exc
        except RESPONSE_SHAPE_ERRORS as exc:
            # Empty/odd payloads (no choices, missing fields) → clean error.
            raise ModelResponseError(
                f"Malformed response from Ollama model '{self._model}'.",
                cause=exc,
            ) from exc

    @property
    def model_name(self) -> str: return self._model

    @property
    def role(self) -> str: return self._role
