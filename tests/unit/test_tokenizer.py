import pytest
from app.utils.tokenizer import estimate_tokens, count_tokens

def test_estimate_tokens_empty():
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
