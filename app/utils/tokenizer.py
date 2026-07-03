"""
Token Counting for JARVIS v2.0

Provides accurate token counting with fallbacks.
Priority:
1. tiktoken (most accurate, OpenAI models)
2. transformers (HuggingFace, good for Llama)
3. word-based fallback (approximate)
"""

from typing import Callable, Optional
from functools import lru_cache


@lru_cache(maxsize=1)
def get_token_counter(model_name: str = "default") -> Callable[[str], int]:
    """
    Get a token counter for the specified model.
    Results are cached - calling again with same model returns same counter.
    
    Args:
        model_name: Model identifier to pick best tokenizer
    
    Returns:
        Function that counts tokens in a string
    """
    # Try tiktoken first (best for OpenAI-compatible models)
    counter = _try_tiktoken(model_name)
    if counter:
        return counter
    
    # Try transformers (good for local Llama models)
    counter = _try_transformers(model_name)
    if counter:
        return counter
    
    # Fallback to word-based estimation
    return _word_counter


def _try_tiktoken(model_name: str) -> Optional[Callable[[str], int]]:
    """Try to use tiktoken for accurate counting"""
    try:
        import tiktoken
        
        # Map common model names to tiktoken encodings
        encoding_map = {
            "gpt-4": "cl100k_base",
            "gpt-4-turbo": "cl100k_base",
            "gpt-3.5-turbo": "cl100k_base",
            "llama": "cl100k_base",  # Approximation, but reasonable
            "default": "cl100k_base",
        }
        
        # Find matching encoding
        encoding_name = "cl100k_base"  # Default
        for key, enc in encoding_map.items():
            if key in model_name.lower():
                encoding_name = enc
                break
        
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding(encoding_name)
        
        def count(text: str) -> int:
            if not text:
                return 0
            return len(encoding.encode(text))
        
        return count
        
    except ImportError:
        return None


def _try_transformers(model_name: str) -> Optional[Callable[[str], int]]:
    """
    Try to use HuggingFace transformers tokenizer.
    Forces OFFLINE mode to prevent any network requests.
    """
    try:
        import os
        # BRUTE FORCE: Tell HuggingFace to never use the network
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        
        from transformers import AutoTokenizer
        
        if "llama" in model_name.lower():
            try:
                # Looks for the model in your local cache ONLY
                tokenizer = AutoTokenizer.from_pretrained(
                    "meta-llama/Meta-Llama-3-8B",
                    use_fast=True,
                    legacy=False,
                    local_files_only=True 
                )
                def count(text: str) -> int:
                    if not text:
                        return 0
                    return len(tokenizer.encode(text, add_special_tokens=False))
                return count
            except Exception:
                pass 
        
        # Fallback to gpt2 (usually comes pre-cached with transformers)
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                "gpt2", 
                use_fast=True, 
                local_files_only=True 
            )
            def count(text: str) -> int:
                if not text:
                    return 0
                return len(tokenizer.encode(text, add_special_tokens=False))
            return count
        except Exception:
            return None
            
    except ImportError:
        return None


def _word_counter(text: str) -> int:
    """
    Word-based token estimation fallback.
    English averages ~1.3 tokens per word.
    Plus small overhead for special tokens.
    """
    if not text:
        return 0
    words = text.split()
    # ~1.3 tokens per word is a reasonable average for English
    # Add 3 for potential special tokens (BOS, EOS, etc.)
    return int(len(words) * 1.3) + 3


def estimate_tokens(text: str, method: str = "auto", model: str = "default") -> int:
    """
    Estimate token count with explicit method selection.
    
    Args:
        text: Text to count
        method: "auto", "tiktoken", "transformers", "word"
        model: Model name for tokenizer selection
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    if method == "tiktoken":
        counter = _try_tiktoken(model) or _word_counter
    elif method == "transformers":
        counter = _try_transformers(model) or _word_counter
    elif method == "word":
        counter = _word_counter
    else:  # "auto"
        counter = get_token_counter(model)
    
    return counter(text)


def get_tokenizer_info() -> dict:
    """
    Get information about available tokenizers.
    Useful for debugging and user feedback.
    """
    import sys
    
    info = {
        "tiktoken_available": "tiktoken" in sys.modules or _try_tiktoken("default") is not None,
        "transformers_available": "transformers" in sys.modules or _try_transformers("default") is not None,
    }
    
    # Test which one we're actually using
    counter = get_token_counter("default")
    test_text = "Hello, world! This is a test."
    count = counter(test_text)
    
    info["active_method"] = "unknown"
    if count == 8:  # tiktoken cl100k_base gives exactly 8
        info["active_method"] = "tiktoken"
    elif count <= 10:  # word-based would give ~9
        info["active_method"] = "word"
    else:
        info["active_method"] = "transformers"
    
    info["test_count"] = count
    return info