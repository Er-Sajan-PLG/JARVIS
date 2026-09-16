"""
Token Counting for JARVIS v2.0

Provides accurate token counting with fallbacks.
Priority:
1. tiktoken (most accurate, OpenAI models)
2. transformers (HuggingFace, good for Llama)
3. word-based fallback (approximate)
"""

import math
from collections.abc import Callable
from functools import lru_cache


@lru_cache(maxsize=128)
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


def _try_tiktoken(model_name: str) -> Callable[[str], int] | None:
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


def _try_transformers(model_name: str) -> Callable[[str], int] | None:
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
                    "meta-llama/Meta-Llama-3-8B", use_fast=True, legacy=False, local_files_only=True
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
            tokenizer = AutoTokenizer.from_pretrained("gpt2", use_fast=True, local_files_only=True)

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
    Word-based token estimation fallback (only used when neither tiktoken nor
    transformers is available).

    This MUST be conservative: under-estimating tokens risks exceeding the
    context window and truncating the conversation. We take the larger of a
    word-based estimate (~1.3 tokens/word for English) and a character-based
    estimate (~4 chars/token), round UP, and add a small constant for special
    tokens. Over-estimating is safe; under-estimating is not.
    """
    if not text:
        return 0
    words = text.split()
    word_estimate = len(words) * 1.3
    char_estimate = len(text) / 4.0
    # ceil() so we never floor our way into an under-count.
    return math.ceil(max(word_estimate, char_estimate)) + 3


count_tokens = lambda text, model="default": estimate_tokens(text, model=model)


def estimate_tokens(text: str, method: str = "auto", model: str = "default") -> int:
    """
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
    info = {
        "tiktoken_available": _try_tiktoken("default") is not None,
        "transformers_available": _try_transformers("default") is not None,
    }

    # The active method is the first available backend in the
    # get_token_counter() priority chain (tiktoken -> transformers -> word).
    # Detect it by identity/availability rather than guessing from a token
    # count, which was fragile (e.g. a <=10 gpt2 count was mislabeled "word").
    counter = get_token_counter("default")
    if counter is _word_counter:
        info["active_method"] = "word"
    elif info["tiktoken_available"]:
        info["active_method"] = "tiktoken"
    elif info["transformers_available"]:
        info["active_method"] = "transformers"
    else:
        info["active_method"] = "unknown"

    test_text = "Hello, world! This is a test."
    info["test_count"] = counter(test_text)
    return info
