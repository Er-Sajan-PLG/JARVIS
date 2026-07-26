# app/models/factory.py

from app.config.settings import ModelConfig
from app.models.client import ModelClient
from app.models.llamacpp_client import LlamaCppClient

# Local backends
try:
    from app.models.ollama_client import OllamaClient
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Cloud backends - OpenAI-compatible
try:
    from app.models.openrouter_client import OpenRouterClient
    OPENROUTER_AVAILABLE = True
except ImportError:
    OPENROUTER_AVAILABLE = False

try:
    from app.models.groq_client import GroqClient
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from app.models.github_models_client import GitHubModelsClient
    GITHUB_MODELS_AVAILABLE = True
except ImportError:
    GITHUB_MODELS_AVAILABLE = False

try:
    from app.models.mistral_client import MistralClient
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

try:
    from app.models.nvidia_nim_client import NVIDIANIMClient
    NVIDIA_NIM_AVAILABLE = True
except ImportError:
    NVIDIA_NIM_AVAILABLE = False

try:
    from app.models.cloudflare_ai_client import CloudflareAIClient
    CLOUDFLARE_AI_AVAILABLE = True
except ImportError:
    CLOUDFLARE_AI_AVAILABLE = False

try:
    from app.models.zhipu_client import ZhipuClient
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False

try:
    from app.models.together_client import TogetherClient
    TOGETHER_AVAILABLE = True
except ImportError:
    TOGETHER_AVAILABLE = False

try:
    from app.models.cerebras_client import CerebrasClient
    CEREBRAS_AVAILABLE = True
except ImportError:
    CEREBRAS_AVAILABLE = False

try:
    from app.models.openai_client import OpenAIClient
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Cloud backends - Custom APIs
try:
    from app.models.google_client import GoogleClient
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from app.models.cohere_client import CohereClient
    COHERE_AVAILABLE = True
except ImportError:
    COHERE_AVAILABLE = False

try:
    from app.models.hf_client import HuggingFaceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

try:
    from app.models.anthropic_client import AnthropicClient
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


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


def create_client(config: ModelConfig, user_keys: dict[str, str] = None) -> ModelClient:
    """Instantiate the correct client based on backend type."""

    # Priority: user_keys (from request header) > config.api_key (env var ref)
    api_key = None
    if user_keys and config.api_key.startswith("env:"):
        var_name = config.api_key[4:].strip()
        api_key = user_keys.get(var_name)
    
    if api_key is None:
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

    # OpenAI-compatible backends
    if config.backend == "openrouter":
        if not OPENROUTER_AVAILABLE:
            raise ImportError("Could not import OpenRouterClient.")
        return OpenRouterClient(
            model=config.name,
            api_key=api_key,  
            role=config.role
        )

    if config.backend == "groq":
        if not GROQ_AVAILABLE:
            raise ImportError("Could not import GroqClient.")
        return GroqClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "github":
        if not GITHUB_MODELS_AVAILABLE:
            raise ImportError("Could not import GitHubModelsClient.")
        return GitHubModelsClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "mistral":
        if not MISTRAL_AVAILABLE:
            raise ImportError("Could not import MistralClient.")
        return MistralClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "nvidia":
        if not NVIDIA_NIM_AVAILABLE:
            raise ImportError("Could not import NVIDIANIMClient.")
        return NVIDIANIMClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "cloudflare":
        if not CLOUDFLARE_AI_AVAILABLE:
            raise ImportError("Could not import CloudflareAIClient.")
        return CloudflareAIClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "zhipu":
        if not ZHIPU_AVAILABLE:
            raise ImportError("Could not import ZhipuClient.")
        return ZhipuClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "together":
        if not TOGETHER_AVAILABLE:
            raise ImportError("Could not import TogetherClient.")
        return TogetherClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "cerebras":
        if not CEREBRAS_AVAILABLE:
            raise ImportError("Could not import CerebrasClient.")
        return CerebrasClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "openai":
        if not OPENAI_AVAILABLE:
            raise ImportError("Could not import OpenAIClient.")
        return OpenAIClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    # Custom API backends
    if config.backend == "google":
        if not GOOGLE_AVAILABLE:
            raise ImportError("Could not import GoogleClient.")
        return GoogleClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "cohere":
        if not COHERE_AVAILABLE:
            raise ImportError("Could not import CohereClient.")
        return CohereClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "huggingface":
        if not HF_AVAILABLE:
            raise ImportError("Could not import HuggingFaceClient.")
        return HuggingFaceClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    if config.backend == "anthropic":
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Could not import AnthropicClient.")
        return AnthropicClient(
            model=config.name,
            api_key=api_key,
            role=config.role
        )

    # Default: llamacpp
    return LlamaCppClient(
        model=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        role=config.role
    )
