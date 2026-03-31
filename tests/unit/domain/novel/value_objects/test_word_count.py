import pytest
from domain.novel.value_objects.word_count import WordCount


def test_word_count_creation():
    """测试创建 WordCount"""
    wc = WordCount(1000)
    assert wc.value == 1000


def test_word_count_negative_raises_error():
    """测试负数字数抛出异常"""
    with pytest.raises(ValueError):
        WordCount(-100)


def test_word_count_addition():
    """测试字数相加"""
    wc1 = WordCount(1000)
    wc2 = WordCount(500)
    result = wc1 + wc2
    assert result.value == 1500


def test_word_count_comparison():
    """测试字数比较"""
    wc1 = WordCount(1000)
    wc2 = WordCount(500)
    wc3 = WordCount(1000)

    assert wc1 > wc2
    assert wc2 < wc1
    assert wc1 == wc3
