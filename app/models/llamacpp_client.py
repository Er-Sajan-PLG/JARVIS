# app/models/llamacpp_client.py
"""
LlamaCpp model client for JARVIS v2.0
"""

from typing import Optional
from openai import OpenAI

from app.models.client import ModelClient, ModelResponse
from app.config.settings import get_settings, get_default_model


class LlamaCppClient(ModelClient):
    """
    Model client for llama.cpp server using OpenAI-compatible API.
    """
    
    def __init__(
        self,
        model: str = None,
        base_url: str = "http://localhost:8080/v1",
        api_key: str = "not-needed",
        role: str = "general"
    ):
        settings = get_settings()
        self._model = model or get_default_model()
        self._role = role
        self._client = OpenAI(base_url=base_url, api_key=api_key)
    
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
    def model_name(self) -> str:
        return self._model
    
    @property
    def role(self) -> str:
        return self._role