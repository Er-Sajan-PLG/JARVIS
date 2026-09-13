"""Unit tests for tokenizer utilities in app/utils/tokenizer.py."""

import builtins
import os
import types
from unittest.mock import MagicMock, patch

import pytest

from app.utils.tokenizer import (
    _try_tiktoken,
    _try_transformers,
    _word_counter,
    count_tokens,
    estimate_tokens,
    get_token_counter,
    get_tokenizer_info,
)


@pytest.fixture(autouse=True)
def clear_token_counter_cache():
    """Ensure LRU cache is clean before and after each test."""
    get_token_counter.cache_clear()
    yield
    get_token_counter.cache_clear()


# ===== _word_counter Tests =====


def test_word_counter_empty():
    """Verify _word_counter returns 0 for empty or falsy strings."""
    assert _word_counter("") == 0
    assert _word_counter(None) == 0


def test_word_counter_word_dominated():
    """Verify _word_counter when word-based count dominates character count."""
    # 10 words: word_estimate = 10 * 1.3 = 13.0, chars = 19 / 4.0 = 4.75 -> ceil(13.0) + 3 = 16
    text = "a b c d e f g h i j"
    assert _word_counter(text) == 16


def test_word_counter_char_dominated():
    """Verify _word_counter when character-based count dominates word count."""
    # 1 long word of 32 chars: word_estimate = 1.3, chars = 32 / 4.0 = 8.0 -> ceil(8.0) + 3 = 11
    text = "abcdefghijklmnopqrstuvwxyz123456"
    assert _word_counter(text) == 11


# ===== _try_tiktoken Tests =====


def test_try_tiktoken_not_installed():
    """Verify _try_tiktoken returns None when tiktoken is not installed."""
    assert _try_tiktoken("default") is None


def test_try_tiktoken_installed_model_exact():
    """Verify _try_tiktoken succeeds when tiktoken is available with exact model match."""
    mock_encoding = MagicMock()
    mock_encoding.encode.return_value = [101, 102, 103]

    mock_tiktoken = types.ModuleType("tiktoken")
    mock_tiktoken.encoding_for_model = MagicMock(return_value=mock_encoding)
    mock_tiktoken.get_encoding = MagicMock()

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tiktoken":
            return mock_tiktoken
        return orig_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        counter = _try_tiktoken("gpt-4")
        assert counter is not None
        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4")
        mock_tiktoken.get_encoding.assert_not_called()

        assert counter("Hello world") == 3
        assert counter("") == 0


def test_try_tiktoken_installed_keyerror_fallback():
    """Verify _try_tiktoken falls back to get_encoding on KeyError from encoding_for_model."""
    mock_encoding = MagicMock()
    mock_encoding.encode.return_value = [201, 202]

    mock_tiktoken = types.ModuleType("tiktoken")
    mock_tiktoken.encoding_for_model = MagicMock(side_effect=KeyError("unknown model"))
    mock_tiktoken.get_encoding = MagicMock(return_value=mock_encoding)

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tiktoken":
            return mock_tiktoken
        return orig_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        counter = _try_tiktoken("unknown-custom-model")
        assert counter is not None
        mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
        assert counter("Test message") == 2


def test_try_tiktoken_encoding_map_prefixes():
    """Verify _try_tiktoken selects appropriate encoding from encoding_map."""
    mock_encoding = MagicMock()
    mock_encoding.encode.return_value = [1]

    mock_tiktoken = types.ModuleType("tiktoken")
    mock_tiktoken.encoding_for_model = MagicMock(side_effect=KeyError("force map lookup"))
    mock_tiktoken.get_encoding = MagicMock(return_value=mock_encoding)

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tiktoken":
            return mock_tiktoken
        return orig_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        for model in ["my-llama-3", "gpt-4-turbo-preview", "gpt-3.5-turbo-0125"]:
            _try_tiktoken(model)
            mock_tiktoken.get_encoding.assert_called_with("cl100k_base")


# ===== _try_transformers Tests =====


def test_try_transformers_llama_success():
    """Verify _try_transformers loads llama tokenizer when model name contains llama."""
    mock_tok = MagicMock()
    mock_tok.encode.return_value = [11, 22, 33, 44]

    with patch(
        "transformers.AutoTokenizer.from_pretrained", return_value=mock_tok
    ) as mock_pretrained:
        counter = _try_transformers("meta-llama-3")
        assert counter is not None
        mock_pretrained.assert_called_once_with(
            "meta-llama/Meta-Llama-3-8B",
            use_fast=True,
            legacy=False,
            local_files_only=True,
        )
        assert counter("Testing llama count") == 4
        assert counter("") == 0
        assert os.environ.get("HF_HUB_OFFLINE") == "1"
        assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"


def test_try_transformers_llama_fails_fallback_to_gpt2():
    """Verify _try_transformers falls back to gpt2 if llama loading fails."""
    mock_gpt2 = MagicMock()
    mock_gpt2.encode.return_value = [100, 200]

    def side_effect(model_id, **kwargs):
        if "llama" in model_id.lower():
            raise RuntimeError("Llama not cached locally")
        return mock_gpt2

    with patch(
        "transformers.AutoTokenizer.from_pretrained", side_effect=side_effect
    ) as mock_pretrained:
        counter = _try_transformers("llama-model")
        assert counter is not None
        assert mock_pretrained.call_count == 2
        assert counter("Fallback test") == 2


def test_try_transformers_non_llama_success():
    """Verify _try_transformers for non-llama models attempts gpt2 directly."""
    mock_tok = MagicMock()
    mock_tok.encode.return_value = [1, 2]

    with patch(
        "transformers.AutoTokenizer.from_pretrained", return_value=mock_tok
    ) as mock_pretrained:
        counter = _try_transformers("general-model")
        assert counter is not None
        mock_pretrained.assert_called_once_with(
            "gpt2",
            use_fast=True,
            local_files_only=True,
        )
        assert counter("Hello") == 2
        assert counter("") == 0


def test_try_transformers_all_fail():
    """Verify _try_transformers returns None when all pretrained attempts raise exceptions."""
    with patch(
        "transformers.AutoTokenizer.from_pretrained", side_effect=Exception("Offline error")
    ):
        assert _try_transformers("llama-model") is None
        assert _try_transformers("other-model") is None


def test_try_transformers_import_error():
    """Verify _try_transformers handles ImportError gracefully without touching sys.modules."""
    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("Simulated transformers missing")
        return orig_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        assert _try_transformers("default") is None


# ===== get_token_counter Tests =====


def test_get_token_counter_priority_tiktoken():
    """Verify get_token_counter prioritizes tiktoken when available."""
    mock_tik = MagicMock(return_value=15)
    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=mock_tik),
        patch("app.utils.tokenizer._try_transformers") as mock_trans,
    ):
        counter = get_token_counter("test-model")
        assert counter is mock_tik
        mock_trans.assert_not_called()


def test_get_token_counter_priority_transformers():
    """Verify get_token_counter uses transformers when tiktoken is unavailable."""
    mock_trans = MagicMock(return_value=12)
    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=None),
        patch("app.utils.tokenizer._try_transformers", return_value=mock_trans),
    ):
        counter = get_token_counter("test-model")
        assert counter is mock_trans


def test_get_token_counter_priority_fallback_word():
    """Verify get_token_counter falls back to _word_counter when both backends unavailable."""
    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=None),
        patch("app.utils.tokenizer._try_transformers", return_value=None),
    ):
        counter = get_token_counter("test-model")
        assert counter is _word_counter


def test_get_token_counter_lru_cache():
    """Verify get_token_counter caches results for identical model names."""
    with patch("app.utils.tokenizer._try_tiktoken", return_value=None) as mock_tik:
        c1 = get_token_counter("cached-model")
        c2 = get_token_counter("cached-model")
        assert c1 is c2
        assert mock_tik.call_count == 1


# ===== estimate_tokens and count_tokens Tests =====


def test_estimate_tokens_empty():
    """Verify estimate_tokens and count_tokens return 0 for empty strings."""
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    assert count_tokens("") == 0


def test_estimate_tokens_methods():
    """Verify estimate_tokens routes correctly across methods."""
    text = "The quick brown fox jumps over the lazy dog"

    # method == "word"
    assert estimate_tokens(text, method="word") == _word_counter(text)

    # method == "tiktoken" with backend available
    mock_tik = MagicMock(return_value=42)
    with patch("app.utils.tokenizer._try_tiktoken", return_value=mock_tik):
        assert estimate_tokens(text, method="tiktoken") == 42

    # method == "tiktoken" with backend unavailable falls back to _word_counter
    with patch("app.utils.tokenizer._try_tiktoken", return_value=None):
        assert estimate_tokens(text, method="tiktoken") == _word_counter(text)

    # method == "transformers" with backend available
    mock_trans = MagicMock(return_value=55)
    with patch("app.utils.tokenizer._try_transformers", return_value=mock_trans):
        assert estimate_tokens(text, method="transformers") == 55

    # method == "transformers" with backend unavailable falls back to _word_counter
    with patch("app.utils.tokenizer._try_transformers", return_value=None):
        assert estimate_tokens(text, method="transformers") == _word_counter(text)

    # method == "auto" delegates to get_token_counter
    with patch("app.utils.tokenizer.get_token_counter", return_value=lambda t: 99):
        assert estimate_tokens(text, method="auto") == 99


def test_count_tokens_convenience():
    """Verify count_tokens calls estimate_tokens with default model."""
    text = "Short text"
    assert count_tokens(text) > 0
    with patch("app.utils.tokenizer.estimate_tokens", return_value=7) as mock_est:
        assert count_tokens(text, model="custom") == 7
        mock_est.assert_called_once_with(text, model="custom")


# ===== get_tokenizer_info Tests =====


def test_get_tokenizer_info_word_active():
    """Verify get_tokenizer_info returns active_method='word' when counter is _word_counter."""
    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=None),
        patch("app.utils.tokenizer._try_transformers", return_value=None),
        patch("app.utils.tokenizer.get_token_counter", return_value=_word_counter),
    ):
        info = get_tokenizer_info()
        assert info["tiktoken_available"] is False
        assert info["transformers_available"] is False
        assert info["active_method"] == "word"
        assert info["test_count"] > 0


def test_get_tokenizer_info_tiktoken_active():
    """Verify get_tokenizer_info returns active_method='tiktoken' when tiktoken is active."""
    mock_fn = MagicMock(return_value=6)
    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=mock_fn),
        patch("app.utils.tokenizer._try_transformers", return_value=None),
        patch("app.utils.tokenizer.get_token_counter", return_value=mock_fn),
    ):
        info = get_tokenizer_info()
        assert info["tiktoken_available"] is True
        assert info["transformers_available"] is False
        assert info["active_method"] == "tiktoken"
        assert info["test_count"] == 6


def test_get_tokenizer_info_transformers_active():
    """Verify get_tokenizer_info returns 'transformers' when transformers is active."""
    mock_fn = MagicMock(return_value=8)
    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=None),
        patch("app.utils.tokenizer._try_transformers", return_value=mock_fn),
        patch("app.utils.tokenizer.get_token_counter", return_value=mock_fn),
    ):
        info = get_tokenizer_info()
        assert info["tiktoken_available"] is False
        assert info["transformers_available"] is True
        assert info["active_method"] == "transformers"
        assert info["test_count"] == 8


def test_get_tokenizer_info_unknown_active():
    """Verify get_tokenizer_info returns 'unknown' when active counter is neither."""

    def custom_counter(s):
        return 10

    with (
        patch("app.utils.tokenizer._try_tiktoken", return_value=None),
        patch("app.utils.tokenizer._try_transformers", return_value=None),
        patch("app.utils.tokenizer.get_token_counter", return_value=custom_counter),
    ):
        info = get_tokenizer_info()
        assert info["tiktoken_available"] is False
        assert info["transformers_available"] is False
        assert info["active_method"] == "unknown"
        assert info["test_count"] == 10
