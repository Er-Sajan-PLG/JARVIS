# app/models/factory.py

from app.config.settings import ModelConfig
from app.models.client import ModelClient
from app.models.llamacpp_client import LlamaCppClient

try:
    from app.models.ollama_client import OllamaClient
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from app.models.openrouter_client import OpenRouterClient
    OPENROUTER_AVAILABLE = True
except ImportError:
    OPENROUTER_AVAILABLE = False

try:
    from app.models.google_client import GoogleClient
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


def _resolve_key(api_key: str) -> str:
    """
    Resolve API key from value or environment variable reference.
    "env:XAI_API_KEY" → reads from os.environ
    "literal-key"           → returned as-is
    """
    import os
    if api_key.startswith("env:"):
        var_name = api_key[4:].strip()
        value = os.environ.get(var_name, "")
        if not value:
            raise ValueError(
                f"Environment variable '{var_name}' is not set.\n"
                f"Add it to your .env file or export it in your shell."
            )
        return value
    return api_key


def create_client(config: ModelConfig) -> ModelClient:
    """Instantiate the correct client based on backend type."""

    api_key = _resolve_key(config.api_key)

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

    if config.backend == "openrouter":
        if not OPENROUTER_AVAILABLE:
            raise ImportError(
                "Could not import OpenRouterClient. "
                "Check app/models/openrouter_client.py exists."
            )
        return OpenRouterClient(
            model=config.name,
            api_key=api_key,  
            role=config.role
        )

    if config.backend == "google":
        if not GOOGLE_AVAILABLE:
            raise ImportError(
                "Could not import GoogleClient. "
                "Check app/models/google_client.py exists and 'requests' is installed."
            )
        return GoogleClient(
            model=config.name,
            api_key=api_key,  # already resolved from env above
            role=config.role
        )

    # Default: llamacpp
    return LlamaCppClient(
        model=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        role=config.role
    )