package httpapi

import (
	"encoding/json"
	"testing"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/domain"
)

func TestDictionaryEntryFromNormalizedRecord(t *testing.T) {
	readings := json.RawMessage(`[
		{"pinyin":"xíng","senses":[
			{"pos":"verb","vi":"đi","definition_vi":"Di chuyển từ nơi này sang nơi khác.","examples":[{"zh":"你先行。","pinyin":"nǐ xiān xíng.","vi":"Bạn đi trước đi."}]},
			{"pos":"adjective","vi":"được, ổn","definition_vi":"Có thể chấp nhận được.","examples":[]}
		]},
		{"pinyin":"háng","senses":[
			{"pos":"noun","vi":"hàng","definition_vi":"Một dãy người hoặc vật.","examples":[{"zh":"请排成一行。","pinyin":"qǐng pái chéng yì háng.","vi":"Hãy xếp thành một hàng."}]}
		]}
	]`)
	record := &domain.NormalizedDictionaryEntry{Simplified: "行", Traditional: "行", Readings: readings}

	entry, err := dictionaryEntryFromRecord("行", record, "我觉得这样也行。", "")
	if err != nil {
		t.Fatal(err)
	}
	if entry.Pinyin == nil || *entry.Pinyin != "xíng" {
		t.Fatalf("unexpected primary pinyin: %#v", entry.Pinyin)
	}
	if len(entry.Meanings) != 3 {
		t.Fatalf("expected 3 meanings, got %d", len(entry.Meanings))
	}
	if entry.PartOfSpeech == nil || *entry.PartOfSpeech != "động từ / tính từ / danh từ" {
		t.Fatalf("unexpected part of speech: %#v", entry.PartOfSpeech)
	}
	if len(entry.Examples) != 2 {
		t.Fatalf("expected 2 examples, got %d", len(entry.Examples))
	}
	if entry.Context == nil || entry.Context.OriginalSentence == nil || *entry.Context.OriginalSentence != "我觉得这样也行。" {
		t.Fatalf("context was not preserved: %#v", entry.Context)
	}
}

func TestDictionaryEntryWithoutSensesDoesNotInventMeaning(t *testing.T) {
	record := &domain.NormalizedDictionaryEntry{
		Simplified:  "㩗",
		Traditional: "携",
		Readings:    json.RawMessage(`[{"pinyin":"xié","senses":[]}]`),
	}

	entry, err := dictionaryEntryFromRecord("㩗", record, "", "")
	if err != nil {
		t.Fatal(err)
	}
	if entry.Meaning != missingDictionaryMeaning {
		t.Fatalf("unexpected fallback meaning: %q", entry.Meaning)
	}
	if entry.EnrichmentError == nil {
		t.Fatal("expected a local dictionary unavailable message")
	}
}

func TestDictionaryEntryRejectsMalformedReadings(t *testing.T) {
	record := &domain.NormalizedDictionaryEntry{Readings: json.RawMessage(`{"bad":true}`)}
	if _, err := dictionaryEntryFromRecord("坏", record, "", ""); err == nil {
		t.Fatal("expected malformed readings to fail")
	}
}

func TestDictionaryEntrySelectsContextualReading(t *testing.T) {
	readings := json.RawMessage(`[
		{"pinyin":"xíng","senses":[{"pos":"verb","vi":"đi","definition_vi":"","examples":[]}]},
		{"pinyin":"háng","senses":[{"pos":"noun","vi":"ngành nghề","definition_vi":"","examples":[]}]}
	]`)
	record := &domain.NormalizedDictionaryEntry{Simplified: "行", Traditional: "行", Readings: readings}

	entry, err := dictionaryEntryFromRecord("行", record, "银行", "háng")
	if err != nil {
		t.Fatal(err)
	}
	if entry.Meaning != "ngành nghề" {
		t.Fatalf("expected háng senses only, got %q", entry.Meaning)
	}
	if entry.Pinyin == nil || *entry.Pinyin != "háng" {
		t.Fatalf("unexpected selected pinyin: %#v", entry.Pinyin)
	}
}

func TestFormatTwoCharacterHeadwordPinyin(t *testing.T) {
	if actual := formatHeadwordPinyin("字幕", "zì mù"); actual != "zìmù" {
		t.Fatalf("unexpected lexical pinyin: %q", actual)
	}
	if actual := formatHeadwordPinyin("超好喝", "chāo hǎo hē"); actual != "chāo hǎo hē" {
		t.Fatalf("phrase spacing should be preserved: %q", actual)
	}
}
