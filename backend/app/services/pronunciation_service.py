from abc import ABC, abstractmethod


class PronunciationProvider(ABC):
    @abstractmethod
    def pinyin_for_sentence(self, text: str) -> list[str | None]:
        raise NotImplementedError

    def pinyin_batch(self, texts: list[str]) -> list[list[str | None]]:
        return [self.pinyin_for_sentence(text) for text in texts]


class PypinyinPronunciationProvider(PronunciationProvider):
    def pinyin_for_sentence(self, text: str) -> list[str | None]:
        from pypinyin import Style, lazy_pinyin

        results = lazy_pinyin(text, style=Style.TONE, errors=lambda chars: list(chars))
        return align_sentence_pinyin(text, results)


def align_sentence_pinyin(text: str, results: list[str | None]) -> list[str | None]:
    if len(results) != len(text):
        raise ValueError(f"Pinyin result length {len(results)} did not match sentence length {len(text)}")
    return [
        value.strip() if is_han_character(char) and isinstance(value, str) and value.strip() else None
        for char, value in zip(text, results, strict=True)
    ]


def token_pinyin(sentence_pinyin: list[str | None], start: int, end: int) -> str | None:
    syllables = [value for value in sentence_pinyin[start:end] if value]
    if not syllables:
        return None
    if len(syllables) == 2:
        return "".join(syllables)
    return " ".join(syllables)


def is_han_character(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x323AF
    )
