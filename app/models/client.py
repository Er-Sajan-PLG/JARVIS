# app/models/client.py
from typing import Protocol, Optional, Callable
from dataclasses import dataclass


@dataclass
class ModelResponse:
    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None


class ModelClient(Protocol):
    """Protocol defining the model client interface"""
    
    def generate(
        self, 
        messages: list[dict], 
        stream: bool = False, 
        on_token: Callable[[str], None] = None,
        **kwargs
    ) -> ModelResponse:
        """Generate a response. If stream=True, calls on_token for each chunk."""
        ...
    
    @property
    def model_name(self) -> str: ...
    
    @property
    def role(self) -> str: ...