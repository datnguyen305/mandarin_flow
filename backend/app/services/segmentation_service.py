import unicodedata
from abc import ABC, abstractmethod


class SegmentationProvider(ABC):
    @abstractmethod
    def segment(self, text: str) -> list[str]:
        raise NotImplementedError


class JiebaSegmentationProvider(SegmentationProvider):
    def __init__(self) -> None:
        try:
            import jieba

            self._jieba = jieba
        except Exception:
            self._jieba = None
        self._known_words = ["今天", "医院", "工作", "学习", "中文", "中国", "老师", "学生", "朋友", "喜欢"]

    def segment(self, text: str) -> list[str]:
        clean_text = "".join(
            ch for ch in text.strip()
            if not ch.isspace() and not unicodedata.category(ch).startswith("P")
        )
        if not clean_text:
            return []
        if self._jieba is not None:
            return [token for token in self._jieba.lcut(clean_text) if token.strip()]
        return self._fallback_segment(clean_text)

    def _fallback_segment(self, text: str) -> list[str]:
        tokens: list[str] = []
        index = 0
        while index < len(text):
            match = next((word for word in sorted(self._known_words, key=len, reverse=True) if text.startswith(word, index)), None)
            if match:
                tokens.append(match)
                index += len(match)
            else:
                tokens.append(text[index])
                index += 1
        return tokens


def locate_tokens(text: str, tokens: list[str]) -> list[dict]:
    located: list[dict] = []
    cursor = 0
    for token in tokens:
        start = text.find(token, cursor)
        if start == -1:
            start = cursor
        end = start + len(token)
        located.append({"text": token, "start_index": start, "end_index": end})
        cursor = end
    return located
