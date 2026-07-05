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
        
        else:
            # BUG 2 FIX: Restructured so this isn't dead code after a return statement
            # --- STREAMING PATH ---
            full_content = ""
            stream_response = self._client.chat.completions.create(
                model=self._model, 
                messages=messages, 
                stream=True, 
                **kwargs
            )
            
            for chunk in stream_response:
                delta = chunk.choices[0].delta.content or ""
                full_content += delta
                if on_token:
                    on_token(delta)
                    
            return ModelResponse(content=full_content, model=self._model)

    @property
    def model_name(self) -> str: return self._model

    @property
    def role(self) -> str: return self._role