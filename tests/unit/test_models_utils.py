"""Unit tests for app/models/utils.py."""

import pytest

from app.models.utils import resolve_env_key


def test_resolve_literal_key():
    assert resolve_env_key("literal-key-12345") == "literal-key-12345"
    assert resolve_env_key("") == ""


def test_resolve_env_key_success(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "secret-value-abc")
    assert resolve_env_key("env:TEST_API_KEY") == "secret-value-abc"


def test_resolve_env_key_strips_var_name(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "secret-value-abc")
    assert resolve_env_key("env:  TEST_API_KEY  ") == "secret-value-abc"


def test_resolve_env_key_missing_raises(monkeypatch):
    monkeypatch.delenv("NON_EXISTENT_VAR", raising=False)
    with pytest.raises(ValueError, match="Environment variable 'NON_EXISTENT_VAR' is not set"):
        resolve_env_key("env:NON_EXISTENT_VAR")


def test_resolve_env_key_empty_value_raises(monkeypatch):
    monkeypatch.setenv("EMPTY_VAR", "")
    with pytest.raises(ValueError, match="Environment variable 'EMPTY_VAR' is not set"):
        resolve_env_key("env:EMPTY_VAR")
