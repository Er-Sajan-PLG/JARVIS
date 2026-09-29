"""
Centralized configuration for JARVIS v2.1
"""

import threading
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model"""

    name: str
    role: str
    backend: str = "llamacpp"
    base_url: str = "http://localhost:8080/v1"
    api_key: str = "not-needed"
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class MemoryConfig:
    """Memory system configuration"""

    max_memories: int = 1000
    retrieval_limit: int = 20
    min_relevance_score: float = 0.1
    min_confidence: float = 0.0
    enable_ranking: bool = True
    candidate_overshoot_factor: int = 3


@dataclass
class ContextConfig:
    """Context window configuration"""

    max_tokens: int = 4096
    safety_margin: int = 100
    compression_threshold: float = 0.8
    tokenizer_method: str = "auto"


@dataclass
class ConversationConfig:
    """Conversation management configuration"""

    max_recent_messages: int = 20
    enable_summarization: bool = False
    save_on_every_message: bool = True


@dataclass
class RetrievalConfig:
    """Memory retrieval configuration"""

    method: str = "keyword"
    keyword_min_overlap: int = 1


@dataclass
class RankingConfig:
    """Memory ranking configuration"""

    weight_relevance: float = 0.35
    weight_importance: float = 0.25
    weight_frequency: float = 0.15
    weight_recency: float = 0.15
    weight_confidence: float = 0.10
    recency_half_life_days: float = 7.0


@dataclass
class OCRConfig:
    """OCR configuration.

    This section exists because its absence was a two-month outage. Both
    previous OCR backends (``paddle_ocr.py``, ``unlimited_ocr.py``) read
    ``self.settings.ocr.*`` across 22 call sites, but ``Settings`` never had an
    ``ocr`` field, so every ``load()`` raised ``AttributeError`` before it could
    import an engine. The backends were dead from the day they were written.

    The engine is now ``tesseract``, which is a system binary rather than a
    model: there are no weights to download, no CUDA device to select, and
    nothing to load, which is what removes the multi-minute blocking load.

    Language is English-only for now (``eng``). ``tesseract`` needs the matching
    traineddata installed; ``eng`` ships with the base package.
    """

    engine: str = "tesseract"
    # Absolute path or bare name; resolved via ``shutil.which`` at load time.
    binary_path: str = "tesseract"
    # Tesseract language code(s), e.g. "eng". Multiple: "eng+deu".
    language: str = "eng"
    # Per-page subprocess timeout. A hung engine must not occupy a worker
    # forever; the previous backend applied no timeout at all.
    page_timeout_seconds: int = 120
    # Below this many characters of native PDF text, a page is treated as
    # scanned and sent to OCR. Keeps digital PDFs fast and OCR-free.
    native_text_min_chars: int = 20
    max_upload_size_mb: int = 100
    allowed_extensions: list[str] = field(
        default_factory=lambda: [
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".tif",
            ".bmp",
            ".webp",
        ]
    )
    thread_pool_workers: int = 2


@dataclass
class PathsConfig:
    """All file paths in one place"""

    data_dir: Path = field(default_factory=lambda: Path("data"))

    # ChromaDB semantic index + Ollama embedding endpoint. Centralized here so
    # main.py, VectorRetriever and ConversationVectorStore share ONE source
    # instead of each hardcoding "data/chroma" / "http://localhost:11434".
    chroma_dir: Path = field(default_factory=lambda: Path("data") / "chroma")
    ollama_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"

    @property
    def memories(self) -> Path:
        return self.data_dir / "memories.json"

    @property
    def conversations_dir(self) -> Path:
        return self.data_dir / "conversations"

    @property
    def default_conversation(self) -> Path:
        return self.conversations_dir / "default.json"


def _safe_dataclass(cls, data, fallback):
    """Build a dataclass from a dict, ignoring unknown keys and using defaults
    for any missing ones. Returns ``fallback`` if ``data`` isn't a mapping or
    construction fails (e.g. wrong type) so a bad section can't crash loading.
    """
    if not isinstance(data, dict):
        logger.warning("config for %s is not a mapping; using defaults", cls.__name__)
        return fallback
    valid = {f.name for f in fields(cls)}
    try:
        return cls(**{k: v for k, v in data.items() if k in valid})
    except (TypeError, ValueError) as e:
        logger.warning("invalid %s config (%s); using defaults", cls.__name__, e)
        return fallback


def _safe_model_config(key, mdata):
    """Build a ModelConfig, tolerating missing required fields (``name``/``role``
    have no defaults) by falling back to the dict ``key``. Returns ``None`` on
    an unrecoverable error so the entry is skipped instead of crashing.
    """
    if not isinstance(mdata, dict):
        logger.warning("model '%s' config is not a mapping; skipping", key)
        return None
    valid = {f.name for f in fields(ModelConfig)}
    merged = dict(mdata)
    merged.setdefault("name", key)
    merged.setdefault("role", key)
    try:
        return ModelConfig(**{k: v for k, v in merged.items() if k in valid})
    except (TypeError, ValueError) as e:
        print(f"Warning: invalid model config '{key}' ({e}); skipping")
        return None


@dataclass
class Settings:
    """Master configuration container"""

    default_model: str = "qwen3-8b.gguf"
    active_profile: str = "default"
    models: dict = field(
        default_factory=lambda: {
            "general": ModelConfig(
                name="llama-3.2-3b-instruct-q4_k_m.gguf",
                role="general",
                backend="llamacpp",
                base_url="http://localhost:8080/v1",
            ),
            "autocomplete": ModelConfig(
                name="qwen2.5-1.5b-instruct-q4_k_m.gguf",
                role="autocomplete",
                backend="llamacpp",
                base_url="http://localhost:8082/v1",
                max_tokens=150,
            ),
        }
    )

    memory: MemoryConfig = field(default_factory=MemoryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    ranking: RankingConfig = field(default_factory=RankingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)

    @classmethod
    def load(cls, path: str | None = None) -> "Settings":
        """Load settings from YAML file, or return hardcoded defaults"""
        if path is None:
            path = "config.yaml"

        yaml_path = Path(path)
        if not yaml_path.exists():
            return cls()  # No config file found, use defaults

        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.warning("failed to parse %s (%s); using defaults", yaml_path, e)
            return cls()
        except OSError as e:
            logger.warning("failed to read %s (%s); using defaults", yaml_path, e)
            return cls()

        if not isinstance(data, dict):
            logger.warning(
                "top-level config in %s is not a mapping; using defaults",
                yaml_path,
            )
            return cls()

        # Start with default settings instance
        settings = cls()

        # Top-level optional scalar fields
        if "default_model" in data and isinstance(data["default_model"], str):
            settings.default_model = data["default_model"]

        # Models — required name/role tolerated via fallback; invalid entries skipped
        if "models" in data:
            if isinstance(data["models"], dict):
                loaded_models = {}
                for key, mdata in data["models"].items():
                    model = _safe_model_config(key, mdata)
                    if model is not None:
                        loaded_models[key] = model
                if loaded_models:
                    settings.models = loaded_models
                else:
                    logger.warning("no valid models in config; using default models")
            else:
                logger.warning("'models' is not a mapping; using default models")

        # Structured sections — all fields have defaults, unknown keys ignored
        if "memory" in data:
            settings.memory = _safe_dataclass(MemoryConfig, data["memory"], settings.memory)
        if "context" in data:
            settings.context = _safe_dataclass(ContextConfig, data["context"], settings.context)
        if "conversation" in data:
            settings.conversation = _safe_dataclass(
                ConversationConfig, data["conversation"], settings.conversation
            )
        if "retrieval" in data:
            settings.retrieval = _safe_dataclass(
                RetrievalConfig, data["retrieval"], settings.retrieval
            )
        if "ranking" in data:
            settings.ranking = _safe_dataclass(RankingConfig, data["ranking"], settings.ranking)
        if "ocr" in data:
            settings.ocr = _safe_dataclass(OCRConfig, data["ocr"], settings.ocr)

        if "active_profile" in data and isinstance(data["active_profile"], str):
            settings.active_profile = data["active_profile"]

        if "profiles" in data:
            logger.warning("'profiles' config is no longer used; ignoring")

        return settings


# Thread-safe singleton
_settings: Settings | None = None
_lock = threading.Lock()


def get_settings() -> Settings:
    """Get the global settings instance (thread-safe)"""
    global _settings
    if _settings is None:
        with _lock:
            if _settings is None:
                _settings = Settings.load()
    return _settings


def reset_settings():
    """Reset settings (useful for testing)"""
    global _settings
    with _lock:
        _settings = None


def get_default_model() -> str:
    return get_settings().default_model
