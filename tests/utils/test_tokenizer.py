import pytest
from app.utils.tokenizer import _word_counter

def test_word_counter_empty():
    assert _word_counter("") == 0
    assert _word_counter(None) == 0

def test_word_counter_simple():
    text = "This is a simple text."
    # 5 words * 1.3 = 6.5
    # 22 chars / 4 = 5.5
    # max(6.5, 5.5) = 6.5
    # math.ceil(6.5) = 7
    # 7 + 3 = 10
    assert _word_counter(text) == 10

def test_word_counter_long_words():
    text = "Supercalifragilisticexpialidocious"
    # 1 word * 1.3 = 1.3
    # 34 chars / 4 = 8.5
    # max(1.3, 8.5) = 8.5
    # math.ceil(8.5) = 9
    # 9 + 3 = 12
    assert _word_counter(text) == 12

def test_word_counter_many_short_words():
    text = "a a a a a a a a a a"
    # 10 words * 1.3 = 13.0
    # 19 chars / 4 = 4.75
    # max(13.0, 4.75) = 13.0
    # math.ceil(13.0) = 13
    # 13 + 3 = 16
    assert _word_counter(text) == 16
