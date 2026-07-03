# app/models/client.py
"""
Base model client interface for JARVIS v2.0
"""

from typing import Protocol, Optional
from dataclasses import dataclass


@dataclass
class ModelResponse:
    """Standardized response from any model"""
    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None


class ModelClient(Protocol):
    """Protocol defining the model client interface"""
    
    def generate(self, messages: list[dict], **kwargs) -> ModelResponse:
        """Generate a response from the model"""
        ...
    
    @property
    def model_name(self) -> str:
        """Return the name/identifier of this model"""
        ...
    
    @property
    def role(self) -> str:
        """Return the role of this model"""
        ...