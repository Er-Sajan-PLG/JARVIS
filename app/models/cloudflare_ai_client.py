"""
Cloudflare Workers AI model client for JARVIS.

Cloudflare Workers AI provides models via OpenAI-compatible API.
https://developers.cloudflare.com/workers-ai/

Usage:
  Set CLOUDFLARE_API_TOKEN in your environment or .env file.
  Set CLOUDFLARE_ACCOUNT_ID in your environment or .env file.
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


class CloudflareAIClient(ModelClient):
    """Model client for Cloudflare Workers AI (OpenAI-compatible)."""

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
                "Cloudflare Workers AI requires an API token.\n"
                "Set CLOUDFLARE_API_TOKEN in your environment or .env file."
            )

        import os

        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        if not account_id:
            raise ValueError(
                "Cloudflare Workers AI requires an account ID.\n"
                "Set CLOUDFLARE_ACCOUNT_ID in your environment or .env file."
            )

        self._base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai"
        self._client = OpenAI(
            base_url=self._base_url,
            api_key=api_key,
        )

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a response via Cloudflare Workers AI."""
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

            full_content = ""
            finish_reason = None
            for chunk in self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                **kwargs,
            ):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                full_content += delta
                if on_token:
                    on_token(delta)
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            if finish_reason is None:
                raise ModelConnectionError(
                    f"Stream from model '{self._model}' ended before completion."
                )
            return ModelResponse(
                content=full_content,
                model=self._model,
                finish_reason=finish_reason,
            )

        except OpenAIError as exc:
            raise map_openai_error(exc, self._model) from exc
        except RESPONSE_SHAPE_ERRORS as exc:
            raise ModelResponseError(
                f"Malformed response from model '{self._model}'.", cause=exc
            ) from exc

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role
