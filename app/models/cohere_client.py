"""
Cohere model client for JARVIS.

Cohere provides models via native API (not OpenAI-compatible).
https://cohere.com/

Usage:
  Set COHERE_API_KEY in your environment or .env file.
"""

from typing import Callable, Optional

import requests

from app.models.client import ModelClient, ModelResponse
from app.models.exceptions import (
    ModelResponseError,
    ModelConnectionError,
)


class CohereClient(ModelClient):
    """Model client for Cohere API."""

    BASE_URL = "https://api.cohere.ai/v1"

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
                "Cohere requires an API key.\n"
                "Set COHERE_API_KEY in your environment or .env file."
            )

        self._api_key = api_key

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a response via Cohere."""
        # Convert OpenAI-style messages to Cohere format
        chat_history = []
        user_message = ""
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                continue  # Cohere doesn't have system role in chat API
            elif role == "user":
                user_message = content
            elif role == "assistant":
                chat_history.append({"role": "USER", "message": user_message})
                chat_history.append({"role": "CHATBOT", "message": content})

        url = f"{self.BASE_URL}/chat"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self._model,
            "message": user_message,
            "chat_history": chat_history,
            "stream": stream,
        }
        
        # Add optional parameters
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        try:
            if not stream:
                res = requests.post(url, json=payload, headers=headers, timeout=120)
                res.raise_for_status()
                data = res.json()
                
                return ModelResponse(
                    content=data.get("text", ""),
                    model=self._model,
                    finish_reason="stop",
                )

            # Streaming
            full_content = ""
            res = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
            res.raise_for_status()
            
            for line in res.iter_lines():
                if not line:
                    continue
                try:
                    import json as json_lib
                    chunk = json_lib.loads(line)
                    if chunk.get("event_type") == "text-generation":
                        text = chunk.get("text", "")
                        full_content += text
                        if on_token:
                            on_token(text)
                except Exception:
                    pass

            return ModelResponse(
                content=full_content,
                model=self._model,
                finish_reason="stop",
            )

        except requests.exceptions.RequestException as exc:
            raise ModelConnectionError(str(exc)) from exc
        except Exception as exc:
            raise ModelResponseError(
                f"Malformed response from Cohere.", cause=exc
            ) from exc

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def role(self) -> str:
        return self._role
