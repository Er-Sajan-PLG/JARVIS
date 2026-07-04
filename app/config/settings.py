"""
Centralized configuration for JARVIS v2.0
"""

import threading
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class ModelConfig:
    """Configuration for a single model"""
    name: str
    role: str
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
    candidate_overshoot_factor: int = 3  # Get 3x candidates before ranking


@dataclass
class ContextConfig:
    """Context window configuration"""
    max_tokens: int = 4096
    safety_margin: int = 100
    compression_threshold: float = 0.8
    tokenizer_method: str = "auto"  # "auto", "tiktoken", "transformers", "word"


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
class PathsConfig:
    """All file paths in one place"""
    data_dir: Path = field(default_factory=lambda: Path("data"))
    
    @property
    def memories(self) -> Path:
        return self.data_dir / "memories.json"
    
    @property
    def conversations_dir(self) -> Path:
        return self.data_dir / "conversations"
    
    @property
    def default_conversation(self) -> Path:
        return self.conversations_dir / "default.json"


@dataclass
class Settings:
    """Master configuration container"""
    default_model: str = "qwen3-8b.gguf"
    
        models: dict = field(default_factory=lambda: {
        "general": ModelConfig(
            name="llama-3.2-3b-instruct-q4_k_m.gguf",
            role="general",
            base_url="http://localhost:8080/v1"  # Main brain
        ),
        "autocomplete": ModelConfig(
            name="qwen2.5-1.5b-instruct-q4_k_m.gguf",
            role="autocomplete",
            base_url="http://localhost:8082/v1", # Fast brain
            max_tokens=150
        ),
        })
    
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    ranking: RankingConfig = field(default_factory=RankingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    
    @classmethod
    def load(cls, path: Optional[str] = None) -> "Settings":
        """Load settings from file, or return defaults"""
        # Future: Load from YAML/JSON/TOML
        return cls()


# Thread-safe singleton
_settings: Optional[Settings] = None
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