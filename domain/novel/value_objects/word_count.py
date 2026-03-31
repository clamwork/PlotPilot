from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WordCount:
    """字数值对象"""
    value: int

    def __post_init__(self):
        if self.value < 0:
            raise ValueError("Word count cannot be negative")

    def __add__(self, other: 'WordCount') -> 'WordCount':
        return WordCount(self.value + other.value)

    def __lt__(self, other: 'WordCount') -> bool:
        return self.value < other.value

    def __le__(self, other: 'WordCount') -> bool:
        return self.value <= other.value

    def __gt__(self, other: 'WordCount') -> bool:
        return self.value > other.value

    def __ge__(self, other: 'WordCount') -> bool:
        return self.value >= other.value
