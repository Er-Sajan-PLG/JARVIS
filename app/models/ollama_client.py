# app/models/ollama_client.py
from typing import Optional, Callable
import ollama

from app.models.client import ModelClient, ModelResponse


class OllamaClient(ModelClient):
    def __init__(self, model: str, base_url: str = "http://localhost:11434", role: str = "general"):
        self._model = model
        self._role = role
        # The ollama python package uses a global client, we configure it here
        self._client = ollama.Client(host=base_url)

    def generate(
        self, 
        messages: list[dict], 
        stream: bool = False, 
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse:
        if not stream:
            response = self._client.chat(model=self._model, messages=messages)
            return ModelResponse(
                content=response["message"]["content"],
                model=self._model,
            )

        # --- Ollama Specific Streaming ---
        full_content = ""
        # Ollama's stream=True yields chunks as dictionaries
        for chunk in self._client.chat(model=self._model, messages=messages, stream=True):
            delta = chunk.get("message", {}).get("content", "")
            full_content += delta
            if on_token:
                on_token(delta)
                
        return ModelResponse(content=full_content, model=self._model)

    @property
    def model_name(self) -> str: return self._model

    @property
    def role(self) -> str: return self._role