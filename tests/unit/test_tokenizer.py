import pytest
from app.utils.tokenizer import estimate_tokens, count_tokens

def test_estimate_tokens_empty():
    """Test that empty string returns 0 tokens."""
    assert estimate_tokens("") == 0
    assert count_tokens("") == 0
    assert estimate_tokens(None) == 0 # type: ignore

def test_estimate_tokens_word_fallback():
    """Test the word-based token estimation fallback."""
    # word_estimate = 2 words * 1.3 = 2.6
    # char_estimate = 11 chars / 4 = 2.75
    # max is 2.75 -> ceil(2.75) = 3 -> 3 + 3 (special tokens) = 6
    assert estimate_tokens("Hello world", method="word") == 6

    # 1 word, 4 chars
    # word_estimate = 1 * 1.3 = 1.3
    # char_estimate = 4 / 4 = 1.0
    # max is 1.3 -> ceil(1.3) = 2 -> 2 + 3 = 5
    assert estimate_tokens("test", method="word") == 5

    # Test longer string with more chars than words
    text = "A" * 100
    # words = 1, char_est = 25, word_est = 1.3
    # max = 25 -> ceil(25) = 25 -> 25 + 3 = 28
    assert estimate_tokens(text, method="word") == 28

def test_estimate_tokens_tiktoken():
    """Test tiktoken method if available, else assert fallback."""
    try:
        import tiktoken
        # "Hello world" with cl100k_base encoding usually is 2 tokens
        count = estimate_tokens("Hello world", method="tiktoken", model="gpt-4")
        # In case tiktoken is successfully used
        assert count == 2
    except ImportError:
        # Fallback should be word counter
        assert estimate_tokens("Hello world", method="tiktoken", model="gpt-4") == 6

def test_estimate_tokens_transformers():
    """Test transformers method if available, else assert fallback."""
    count = estimate_tokens("Hello world", method="transformers", model="gpt2")
    # Will be 2 if transformers is available, or 6 if fallback. We just check > 0
    assert count > 0
    assert count in (2, 6)

def test_estimate_tokens_auto():
    """Test auto method, which chooses the best available."""
    count = estimate_tokens("Hello world", method="auto")
    assert count > 0

def test_count_tokens_alias():
    """Test the count_tokens lambda alias works identical to estimate_tokens."""
    assert count_tokens("Hello world") == estimate_tokens("Hello world", model="default")
    assert count_tokens("Testing model override", model="gpt-4") == estimate_tokens("Testing model override", model="gpt-4")
