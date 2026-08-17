"""
LlamaCpp model client for JARVIS v2.0
"""

from typing import Optional, Callable
from openai import OpenAI, OpenAIError

from app.models.client import ModelClient, ModelResponse
from app.config.settings import get_default_model
from app.models.exceptions import (
    ModelResponseError,
    ModelConnectionError,
    RESPONSE_SHAPE_ERRORS,
    map_openai_error,
)
from app.models.utils import resolve_env_key



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
        self._model = model or get_default_model()
        self._role = role
        
        try:
            api_key = resolve_env_key(api_key)
        except ValueError:
            # If the environment variable is not set, we keep the original string
            # to match the old behavior where os.environ.get returned the default.
            pass

        self._api_key = api_key  
        self._client = OpenAI(base_url=base_url, api_key=api_key)
    
    def generate(
        self, 
        messages: list[dict], 
        stream: bool = False, 
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse:
        
        try:
            # =========================================================
            # 🔵 OPENAI-COMPATIBLE BLOCK (LOCAL, GROK, OPENROUTER)
            # Non-streaming + streaming paths share the same OpenAI SDK.
            # (Google Gemini is handled by app/models/google_client.py.)
            # =========================================================
            if not stream:
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
                        f"Stream from model '{self._model}' ended before "
                        f"completion (received {len(full_content)} chars, "
                        f"no finish reason)."
                    )
                return ModelResponse(
                    content=full_content,
                    model=self._model,
                    finish_reason=finish_reason,
                )
            # =========================================================

        except OpenAIError as exc:
            # Connection errors, timeouts, rate limits, API/status errors →
            # a single typed ModelError rather than a raw openai exception.
            raise map_openai_error(exc, self._model) from exc
        except RESPONSE_SHAPE_ERRORS as exc:
            # Empty/odd payloads (no choices, missing fields) → clean error.
            raise ModelResponseError(
                f"Malformed response from model '{self._model}'.", cause=exc
            ) from exc

    
    @property
    def model_name(self) -> str:
        return self._model
    
    @property
    def role(self) -> str:
        return self._role