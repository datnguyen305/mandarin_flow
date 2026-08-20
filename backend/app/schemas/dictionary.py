from pydantic import BaseModel


class DictionaryMeaning(BaseModel):
    meaning: str
    definition: str | None = None


class DictionaryContext(BaseModel):
    original_sentence: str | None = None
    selected_meaning: str | None = None
    phrase: str | None = None
    phrase_pinyin: str | None = None
    phrase_meaning: str | None = None
    explanation: str | None = None


class DictionaryCollocation(BaseModel):
    text: str
    pinyin: str
    meaning: str


class DictionaryExample(BaseModel):
    chinese: str
    pinyin: str
    vietnamese: str


class DictionaryEnrichment(BaseModel):
    part_of_speech: str | None = None
    context: DictionaryContext | None = None
    collocations: list[DictionaryCollocation] = []
    examples: list[DictionaryExample] = []


class DictionaryEntry(BaseModel):
    word: str
    pinyin: str | None = None
    meaning: str
    part_of_speech: str | None = None
    contextual_meaning: str | None = None
    example_zh: str | None = None
    example_vi: str | None = None
    meanings: list[DictionaryMeaning] = []
    context: DictionaryContext | None = None
    collocations: list[DictionaryCollocation] = []
    examples: list[DictionaryExample] = []
    enrichment_error: str | None = None
