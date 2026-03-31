from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterContent:
    """章节内容值对象"""
    raw_text: str

    def __post_init__(self):
        if self.raw_text is None:
            raise ValueError("Chapter content cannot be None")

    def word_count(self) -> int:
        """计算字数（简单实现）"""
        return len(self.raw_text)
