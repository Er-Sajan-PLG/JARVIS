"""
GitHub Models client for JARVIS.

GitHub Models provides free access to popular models via OpenAI-compatible API.
https://github.com/marketplace/models

Usage:
  Set GITHUB_TOKEN in your environment or .env file.
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


class GitHubModelsClient(ModelClient):
    """Model client for GitHub Models (OpenAI-compatible)."""

    BASE_URL = "https://models.inference.ai.azure.com"

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
                "GitHub Models requires a GitHub token.\n"
                "Set GITHUB_TOKEN in your environment or .env file."
            )

        self._client = OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a response via GitHub Models."""
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
