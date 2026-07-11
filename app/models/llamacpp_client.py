"""
LlamaCpp model client for JARVIS v2.0
"""

from typing import Optional, Callable
from openai import OpenAI

from app.models.client import ModelClient, ModelResponse
from app.config.settings import get_default_model



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
        
        # --- FIX: Resolve "env:..." to actual key ---
        if api_key.startswith("env:"):
            import os
            api_key = os.environ.get(api_key[4:].strip(), api_key)
        # ---------------------------------------------
        
        self._api_key = api_key  
        self._client = OpenAI(base_url=base_url, api_key=api_key)
    
    def generate(
        self, 
        messages: list[dict], 
        stream: bool = False, 
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse:
        

        # =========================================================
        # 🟡 ISOLATED GOOGLE BLOCK
        # (Unhash this to use Google. Hash the OpenAI block below!)
        # =========================================================
        # import requests, json
        # 
        # google_messages = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages]
        # 
        # if not stream:
        #     url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        #     res = requests.post(url, json={"contents": google_messages})
        #     data = res.json()
        #     
        #     # Stops the ugly KeyError if Google complains
        #     if "error" in data:
        #         raise Exception(f"Google API Error: {data['error']['message']}")
        #         
        #     content = data["candidates"][0]["content"]["parts"][0]["text"]
        #     return ModelResponse(content=content, model=self._model, tokens_used=None, finish_reason="stop")
        #     
        # else:
        #     url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:streamGenerateContent?alt=sse&key={self._api_key}"
        #     res = requests.post(url, json={"contents": google_messages}, stream=True)
        #     full_content = ""
        #     for line in res.iter_lines():
        #         if line:
        #             line = line.decode("utf-8")
        #             if line.startswith("data: "):
        #                 chunk_str = line[6:]
        #                 if chunk_str == "[DONE]": break
        #                 try:
        #                     chunk = json.loads(chunk_str)
        #                     delta = chunk["candidates"][0]["content"]["parts"][0].get("text", "")
        #                     full_content += delta
        #                     if on_token: on_token(delta)
        #                 except: pass
        #     return ModelResponse(content=full_content, model=self._model)
        # =========================================================



        # =========================================================
        # 🔵 OPENAI-COMPATIBLE BLOCK (LOCAL, GROK, OPENROUTER)
        # (Unhash this to use Grok or Local. Hash the Google block above!)
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
        # =========================================================

    
    @property
    def model_name(self) -> str:
        return self._model
    
    @property
    def role(self) -> str:
        return self._role