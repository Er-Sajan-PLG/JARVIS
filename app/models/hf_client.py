"""
Hugging Face model client for JARVIS.

Hugging Face provides models via Inference API.
https://huggingface.co/inference-api

Usage:
  Set HF_API_TOKEN in your environment or .env file.
"""

from collections.abc import Callable

import requests

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)


class HuggingFaceClient(ModelClient):
    """Model client for Hugging Face Inference API."""

    BASE_URL = "https://api-inference.huggingface.co"

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
                "Hugging Face requires an API token.\n"
                "Set HF_API_TOKEN in your environment or .env file."
            )

        self._api_key = api_key

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a response via Hugging Face."""
        # Convert messages to a simple prompt
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"[SYSTEM]: {content}\n"
            elif role == "user":
                prompt += f"[USER]: {content}\n"
            elif role == "assistant":
                prompt += f"[ASSISTANT]: {content}\n"

        url = f"{self.BASE_URL}/models/{self._model}"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        payload = {"inputs": prompt}
        if "temperature" in kwargs:
            payload["parameters"] = {"temperature": kwargs["temperature"]}
        if "max_tokens" in kwargs:
            if "parameters" not in payload:
                payload["parameters"] = {}
            payload["parameters"]["max_new_tokens"] = kwargs["max_tokens"]

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=120)
            res.raise_for_status()
            data = res.json()

            # Handle different response formats
            if isinstance(data, list) and len(data) > 0:
                output = data[0]
                if isinstance(output, dict):
                    content = output.get("generated_text", "")
                else:
                    content = str(output)
            else:
                content = str(data)

            if on_token:
                on_token(content)

            return ModelResponse(
                content=content,
                model=self._model,
                finish_reason="stop",
            )

        except requests.exceptions.RequestException as exc:
            raise ModelConnectionError(str(exc)) from exc
        except Exception as exc:
            raise ModelResponseError("Malformed response from Hugging Face.", cause=exc) from exc

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role
