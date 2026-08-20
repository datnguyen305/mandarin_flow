import pytest

from app.services.dictionary_service import CVDictDictionaryProvider, clean_cvdict_meaning, load_cvdict_index, numbered_pinyin_to_marks


def test_numbered_pinyin_to_marks() -> None:
    assert numbered_pinyin_to_marks("yi1 yuan4") == "yī yuàn"
    assert numbered_pinyin_to_marks("xue2 xi2") == "xué xí"
    assert numbered_pinyin_to_marks("nu:3") == "nǚ"


def test_clean_cvdict_meaning_removes_classifier_metadata() -> None:
    assert clean_cvdict_meaning("bệnh viện/LT:所[suo3],家[jia1]/") == "bệnh viện"


def test_load_cvdict_index_supports_simplified_and_traditional(tmp_path) -> None:
    dictionary_file = tmp_path / "CVDICT.u8"
    dictionary_file.write_text(
        "# comment\n醫院 医院 [yi1 yuan4] /bệnh viện/\n學習 学习 [xue2 xi2] /học tập/\n",
        encoding="utf-8",
    )

    load_cvdict_index.cache_clear()
    index = load_cvdict_index(str(dictionary_file))

    assert index["医院"][0]["meaning"] == "bệnh viện"
    assert index["醫院"][0]["simplified"] == "医院"


@pytest.mark.asyncio
async def test_cvdict_lookup_returns_vietnamese_meaning(tmp_path) -> None:
    dictionary_file = tmp_path / "CVDICT.u8"
    dictionary_file.write_text("醫院 医院 [yi1 yuan4] /bệnh viện/\n", encoding="utf-8")

    load_cvdict_index.cache_clear()
    provider = CVDictDictionaryProvider(path=str(dictionary_file))
    entry = await provider.lookup("医院", "我在医院工作")

    assert entry.word == "医院"
    assert entry.pinyin == "yīyuàn"
    assert entry.meaning == "bệnh viện"
    assert entry.meanings[0].meaning == "bệnh viện"
