"""BaseLLMProvider Interface & Data Contracts for Multi-Provider Inference Subsystem.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator


@dataclass
class LLMResponse:
    """Standardized response container from any LLM provider."""
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Abstract Base Class / Interface for all multi-provider LLM adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name string of the provider (e.g., 'google', 'groq', 'openrouter', 'ollama')."""
        pass

    @abstractmethod
    async def is_available(self, api_key: str | None = None) -> bool:
        """Check if provider is configured and available for requests."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Generate complete text response from LLM provider."""
        pass

    @abstractmethod
    async def stream_text(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream token chunks asynchronously from LLM provider."""
        pass
