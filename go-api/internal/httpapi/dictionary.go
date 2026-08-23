package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/domain"
	"github.com/datnguyen305/mandarin-flow/go-api/internal/store"
)

const missingDictionaryMeaning = "Chưa có nghĩa tiếng Việt."

type normalizedReading struct {
	Pinyin string            `json:"pinyin"`
	Senses []normalizedSense `json:"senses"`
}

type normalizedSense struct {
	POS          string              `json:"pos"`
	VI           string              `json:"vi"`
	DefinitionVI string              `json:"definition_vi"`
	Examples     []normalizedExample `json:"examples"`
}

type normalizedExample struct {
	ZH     string `json:"zh"`
	Pinyin string `json:"pinyin"`
	VI     string `json:"vi"`
}

func (api *nativeAPI) lookupDictionary(writer http.ResponseWriter, request *http.Request) {
	word := strings.TrimSpace(request.PathValue("word"))
	if word == "" {
		writeError(writer, http.StatusUnprocessableEntity, "validation_error", "Dictionary word is required")
		return
	}

	record, err := api.deps.Store.LookupNormalizedDictionary(request.Context(), word)
	if errors.Is(err, store.ErrNotFound) {
		writeJSON(writer, http.StatusOK, missingDictionaryEntry(word))
		return
	}
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}

	entry, err := dictionaryEntryFromRecord(
		word,
		record,
		request.URL.Query().Get("context"),
		request.URL.Query().Get("pinyin"),
	)
	if err != nil {
		api.logger.Error("invalid normalized dictionary entry", "word", word, "error", err)
		writeJSON(writer, http.StatusOK, missingDictionaryEntry(word))
		return
	}
	writeJSON(writer, http.StatusOK, entry)
}

func dictionaryEntryFromRecord(word string, record *domain.NormalizedDictionaryEntry, context, requestedPinyin string) (domain.DictionaryEntry, error) {
	var readings []normalizedReading
	if err := json.Unmarshal(record.Readings, &readings); err != nil {
		return domain.DictionaryEntry{}, err
	}

	readings = readingsForPinyin(readings, requestedPinyin)
	meanings := make([]domain.DictionaryMeaning, 0)
	examples := make([]domain.DictionaryExample, 0)
	seenMeanings := make(map[string]struct{})
	seenExamples := make(map[string]struct{})
	seenPOS := make(map[string]struct{})
	partsOfSpeech := make([]string, 0)
	var pinyin *string

	for _, reading := range readings {
		readingPinyin := strings.TrimSpace(reading.Pinyin)
		if pinyin == nil && readingPinyin != "" {
			pinyin = stringPointer(formatHeadwordPinyin(word, readingPinyin))
		}
		for _, sense := range reading.Senses {
			meaning := strings.TrimSpace(sense.VI)
			if meaning == "" {
				continue
			}
			key := strings.ToLower(meaning)
			if _, exists := seenMeanings[key]; !exists {
				seenMeanings[key] = struct{}{}
				var definition *string
				if value := strings.TrimSpace(sense.DefinitionVI); value != "" {
					definition = stringPointer(value)
				}
				meanings = append(meanings, domain.DictionaryMeaning{Meaning: meaning, Definition: definition})
			}

			if pos := vietnamesePartOfSpeech(sense.POS); pos != "" {
				if _, exists := seenPOS[pos]; !exists {
					seenPOS[pos] = struct{}{}
					partsOfSpeech = append(partsOfSpeech, pos)
				}
			}

			for _, example := range sense.Examples {
				zh := strings.TrimSpace(example.ZH)
				if zh == "" || strings.TrimSpace(example.Pinyin) == "" || strings.TrimSpace(example.VI) == "" {
					continue
				}
				if _, exists := seenExamples[zh]; exists {
					continue
				}
				seenExamples[zh] = struct{}{}
				examples = append(examples, domain.DictionaryExample{
					Chinese:    zh,
					Pinyin:     strings.TrimSpace(example.Pinyin),
					Vietnamese: strings.TrimSpace(example.VI),
				})
			}
		}
	}

	if len(meanings) == 0 {
		return missingDictionaryEntry(word), nil
	}

	meaningTexts := make([]string, 0, len(meanings))
	for _, meaning := range meanings {
		meaningTexts = append(meaningTexts, meaning.Meaning)
	}
	var partOfSpeech *string
	if len(partsOfSpeech) > 0 {
		partOfSpeech = stringPointer(strings.Join(partsOfSpeech, " / "))
	}
	var dictionaryContext *domain.DictionaryContext
	if value := strings.TrimSpace(context); value != "" {
		dictionaryContext = &domain.DictionaryContext{OriginalSentence: stringPointer(value)}
	}

	return domain.DictionaryEntry{
		Word:         word,
		Pinyin:       pinyin,
		Meaning:      strings.Join(meaningTexts, "; "),
		PartOfSpeech: partOfSpeech,
		Meanings:     meanings,
		Context:      dictionaryContext,
		Collocations: []any{},
		Examples:     examples,
	}, nil
}

func missingDictionaryEntry(word string) domain.DictionaryEntry {
	message := "Từ này chưa có trong nguồn từ điển đã chuẩn hóa."
	return domain.DictionaryEntry{
		Word:            word,
		Meaning:         missingDictionaryMeaning,
		Meanings:        []domain.DictionaryMeaning{},
		Collocations:    []any{},
		Examples:        []domain.DictionaryExample{},
		EnrichmentError: &message,
	}
}

func vietnamesePartOfSpeech(value string) string {
	parts := map[string]string{
		"noun": "danh từ", "verb": "động từ", "adjective": "tính từ",
		"adverb": "trạng từ", "pronoun": "đại từ", "preposition": "giới từ",
		"conjunction": "liên từ", "particle": "trợ từ", "classifier": "lượng từ",
		"numeral": "số từ", "interjection": "thán từ", "idiom": "thành ngữ",
		"phrase": "cụm từ", "proper_noun": "danh từ riêng", "auxiliary": "trợ động từ",
		"modal": "động từ năng nguyện", "onomatopoeia": "từ tượng thanh",
	}
	return parts[strings.TrimSpace(value)]
}

func formatHeadwordPinyin(word, pinyin string) string {
	if len([]rune(word)) == 2 && len(strings.Fields(pinyin)) == 2 {
		return strings.Join(strings.Fields(pinyin), "")
	}
	return pinyin
}

func readingsForPinyin(readings []normalizedReading, requested string) []normalizedReading {
	normalizedRequested := normalizePinyin(requested)
	if normalizedRequested == "" {
		return readings
	}
	matches := make([]normalizedReading, 0, 1)
	for _, reading := range readings {
		if normalizePinyin(reading.Pinyin) == normalizedRequested {
			matches = append(matches, reading)
		}
	}
	if len(matches) == 0 {
		return readings
	}
	return matches
}

func normalizePinyin(value string) string {
	replacer := strings.NewReplacer(" ", "", "'", "", "’", "")
	return strings.ToLower(replacer.Replace(strings.TrimSpace(value)))
}

func stringPointer(value string) *string {
	return &value
}
