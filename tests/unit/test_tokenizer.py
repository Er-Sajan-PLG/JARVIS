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
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0

def test_estimate_tokens_word_method():
    # word_estimate = 4 * 1.3 = 5.2
    # char_estimate = 14 / 4.0 = 3.5
    # max = 5.2 -> ceil(5.2) = 6. 6 + 3 = 9
    text1 = "this is a test"
    assert estimate_tokens(text1, method="word") == 9

    # word_estimate = 1 * 1.3 = 1.3
    # char_estimate = 34 / 4.0 = 8.5
    # max = 8.5 -> ceil(8.5) = 9. 9 + 3 = 12
    text2 = "supercalifragilisticexpialidocious"
    assert estimate_tokens(text2, method="word") == 12

def test_estimate_tokens_other_methods():
    text = "Hello world"

    # "auto" should not raise exceptions
    auto_result = estimate_tokens(text, method="auto")
    assert isinstance(auto_result, int)
    assert auto_result > 0

    # "tiktoken" should fall back or work
    tik_result = estimate_tokens(text, method="tiktoken")
    assert isinstance(tik_result, int)
    assert tik_result > 0

    # "transformers" should fall back or work
    trans_result = estimate_tokens(text, method="transformers")
    assert isinstance(trans_result, int)
    assert trans_result > 0

def test_count_tokens_alias():
    # count_tokens is an alias to estimate_tokens(text, model="default")
    result = count_tokens("test string")
    assert isinstance(result, int)
    assert result > 0
