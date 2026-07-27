"""Model Router & Provider Failover Pool for Multi-Provider Inference.

Routes task requests dynamically to healthy LLM providers and handles circuit breaker failover on 429/503 errors.
"""

from enum import Enum
import logging
from typing import Any, AsyncGenerator, Dict

from app.models.interface import BaseLLMProvider, LLMResponse
from app.resources import ResourceManager

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task category classification for model routing."""
    AUTOCOMPLETE = "autocomplete"
    CODE = "code"
    REASONING = "reasoning"
    STEM = "stem"
    GENERAL = "general"
    DOCS = "docs"


class ModelRouter:
    """Routes prompt requests across registered LLM providers with automatic circuit breaker failover."""

    KEYWORDS: dict[TaskType, list[str]] = {
        TaskType.CODE: [
            "code", "function", "class", "bug", "error", "debug",
            "implement", "program", "script", "syntax", "compile",
            "refactor", "variable", "method", "algorithm", "api"
        ],
        TaskType.STEM: [
            "math", "calculate", "equation", "physics", "chemistry",
            "formula", "theorem", "proof", "derivative", "integral"
        ],
        TaskType.REASONING: [
            "think", "analyze", "reason", "logic", "compare",
            "evaluate", "justify", "argument", "conclusion", "infer"
        ],
        TaskType.DOCS: [
            "document", "readme", "docs", "tutorial", "walkthrough"
        ],
        TaskType.GENERAL: ["general"],
        TaskType.AUTOCOMPLETE: ["autocomplete"],
    }

    def __init__(self, resource_manager: ResourceManager | None = None) -> None:
        self.providers: dict[str, BaseLLMProvider] = {}
        self.resource_manager = resource_manager or ResourceManager()
        self.default_provider_name: str | None = None

    def register_provider(self, provider: BaseLLMProvider, default: bool = False) -> None:
        """Register an LLM provider implementation."""
        name = provider.provider_name
        self.providers[name] = provider
        if default or not self.default_provider_name:
            self.default_provider_name = name
        logger.info("Registered LLM provider '%s' (Default: %s)", name, default)

    def select_healthy_provider(self, preferred_provider: str | None = None) -> BaseLLMProvider:
        """Select a healthy provider respecting circuit breaker status.

        Args:
            preferred_provider: Desired provider name if healthy.

        Returns:
            BaseLLMProvider instance.

        Raises:
            RuntimeError: If no healthy providers are available.
        """
        # 1. Check preferred provider
        if preferred_provider and preferred_provider in self.providers:
            if self.resource_manager.health.is_available(preferred_provider):
                return self.providers[preferred_provider]

        # 2. Check default provider
        if self.default_provider_name and self.default_provider_name in self.providers:
            if self.resource_manager.health.is_available(self.default_provider_name):
                return self.providers[self.default_provider_name]

        # 3. Failover pool check
        for name, provider in self.providers.items():
            if self.resource_manager.health.is_available(name):
                logger.info("Failing over to available provider '%s'", name)
                return provider

        raise RuntimeError("No healthy LLM providers available in failover pool")

    async def generate(
        self,
        prompt: str,
        model: str,
        preferred_provider: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key: str | None = None,
    ) -> LLMResponse:
        """Generate response with automatic provider failover on 429/503 errors."""
        provider = self.select_healthy_provider(preferred_provider)
        provider_name = provider.provider_name

        try:
            res = await provider.generate_text(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
            )
            self.resource_manager.health.record_success(provider_name)
            self.resource_manager.rate_limits.record_request(provider_name, res.total_tokens)
            return res
        except Exception as err:
            err_str = str(err)
            code = 429 if "429" in err_str or "rate limit" in err_str.lower() else (503 if "503" in err_str else None)
            self.resource_manager.health.record_failure(provider_name, code)
            logger.warning("Provider '%s' failed (%s). Retrying with failover...", provider_name, err)

            # Retry with fallback
            fallback = self.select_healthy_provider(preferred_provider=None)
            res = await fallback.generate_text(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
            )
            self.resource_manager.health.record_success(fallback.provider_name)
            return res

    def classify_prompt(self, prompt: str) -> TaskType:
        """Classify prompt into TaskType based on keyword scoring."""
        text = prompt.lower()
        scores: dict[TaskType, int] = {}

        for task_type, keywords in self.KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[task_type] = score

        if not scores:
            return TaskType.GENERAL

        return max(scores, key=lambda k: scores[k])
