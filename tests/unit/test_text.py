import pytest
from app.utils.text import extract_keywords

def test_extract_keywords_empty():
    assert extract_keywords("") == set()
    assert extract_keywords(None) == set()

def test_extract_keywords_basic():
    text = "Hello world! This is a test."
    # The default stop_words includes "this", "is", "a"
    # "hello", "world", "test" are kept
    assert extract_keywords(text) == {"hello", "world", "test"}

def test_extract_keywords_punctuation():
    text = "Hello, world!!! This... is a test!?"
    assert extract_keywords(text) == {"hello", "world", "test"}

def test_extract_keywords_single_chars():
    text = "a b c d e f g hello h i j k l m n o p q r s t u v w x y z"
    # Even if stop_words is empty, single chars are filtered out
    assert extract_keywords(text, stop_words=[]) == {"hello"}

def test_extract_keywords_custom_stop_words():
    text = "Hello world! This is a test."
    assert extract_keywords(text, stop_words=["hello", "world"]) == {"this", "is", "test"}

def test_extract_keywords_case_insensitive():
    text = "HELLO WORLD TEST Test test Hello"
    assert extract_keywords(text, stop_words=[]) == {"hello", "world", "test"}
