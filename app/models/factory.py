# app/models/factory.py
"""
Factory to instantiate the correct model client based on config.
Keeps main.py completely blind to backend specifics.
"""

from app.config.settings import ModelConfig
from app.models.client import ModelClient
from app.models.llamacpp_client import LlamaCppClient

# We try to import Ollama, but it's okay if it's not installed yet.
# JARVIS will crash only if the user actually tries to use an ollama model.
try:
    from app.models.ollama_client import OllamaClient
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def create_client(config: ModelConfig) -> ModelClient:
    """Instantiate the correct client based on backend type."""
    if config.backend == "ollama":
        if not OLLAMA_AVAILABLE:
            raise ImportError(
                "The 'ollama' python package is required for OllamaClient. "
                "Run: pip install ollama"
            )
        return OllamaClient(
            model=config.name,
            base_url=config.base_url,
            role=config.role
        )
    
    # Default to llamacpp (OpenAI compatible)
    return LlamaCppClient(
        model=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        role=config.role
    )