package domain

import (
	"encoding/json"
	"time"
)

type Guest struct {
	ID         string
	LastSeenAt time.Time
}

type Video struct {
	ID                int64      `json:"id"`
	YouTubeVideoID    string     `json:"youtube_video_id"`
	Title             string     `json:"title"`
	URL               string     `json:"url"`
	ThumbnailURL      *string    `json:"thumbnail_url"`
	DurationSeconds   *int32     `json:"duration_seconds"`
	ChannelName       *string    `json:"channel_name"`
	ChannelID         *string    `json:"channel_id"`
	UploadDate        *time.Time `json:"upload_date"`
	MetadataFetchedAt *time.Time `json:"metadata_fetched_at"`
	Language          string     `json:"language"`
	ProcessingStatus  string     `json:"processing_status"`
	Tags              []string   `json:"tags"`
	CreatedAt         time.Time  `json:"created_at"`
}

type SubtitleToken struct {
	Text       string  `json:"text"`
	Pinyin     *string `json:"pinyin"`
	Meaning    *string `json:"meaning"`
	StartIndex *int    `json:"start_index"`
	EndIndex   *int    `json:"end_index"`
}

type SubtitleLine struct {
	ID               int64           `json:"id"`
	Start            float64         `json:"start"`
	End              float64         `json:"end"`
	Text             string          `json:"text"`
	Translation      *string         `json:"translation"`
	Tokens           []SubtitleToken `json:"tokens"`
	ProcessingStatus string          `json:"processing_status"`
}

type SubtitleResponse struct {
	VideoID   string         `json:"video_id"`
	Title     string         `json:"title"`
	Subtitles []SubtitleLine `json:"subtitles"`
}

type VideoProgress struct {
	YouTubeVideoID string    `json:"youtube_video_id"`
	CurrentTime    float64   `json:"current_time"`
	Completed      bool      `json:"completed"`
	LastWatchedAt  time.Time `json:"last_watched_at"`
}

type SaveVocabularyInput struct {
	Word           string  `json:"word"`
	Pinyin         *string `json:"pinyin"`
	Meaning        *string `json:"meaning"`
	YouTubeVideoID string  `json:"youtube_video_id"`
	SubtitleID     int64   `json:"subtitle_id"`
	Timestamp      float64 `json:"timestamp"`
}

type SavedVocabulary struct {
	ID               int64     `json:"id"`
	Word             string    `json:"word"`
	Pinyin           *string   `json:"pinyin"`
	Meaning          *string   `json:"meaning"`
	YouTubeVideoID   string    `json:"youtube_video_id"`
	VideoTitle       string    `json:"video_title"`
	SubtitleSentence string    `json:"subtitle_sentence"`
	Timestamp        float64   `json:"timestamp"`
	CreatedAt        time.Time `json:"created_at"`
}

type NormalizedDictionaryEntry struct {
	Simplified  string
	Traditional string
	Readings    json.RawMessage
	HSKLevel    *int16
}

type DictionaryMeaning struct {
	Meaning    string  `json:"meaning"`
	Definition *string `json:"definition,omitempty"`
}

type DictionaryContext struct {
	OriginalSentence *string `json:"original_sentence,omitempty"`
}

type DictionaryExample struct {
	Chinese    string `json:"chinese"`
	Pinyin     string `json:"pinyin"`
	Vietnamese string `json:"vietnamese"`
}

type DictionaryEntry struct {
	Word              string              `json:"word"`
	Pinyin            *string             `json:"pinyin"`
	Meaning           string              `json:"meaning"`
	PartOfSpeech      *string             `json:"part_of_speech"`
	ContextualMeaning *string             `json:"contextual_meaning"`
	ExampleZH         *string             `json:"example_zh"`
	ExampleVI         *string             `json:"example_vi"`
	Meanings          []DictionaryMeaning `json:"meanings"`
	Context           *DictionaryContext  `json:"context"`
	Collocations      []any               `json:"collocations"`
	Examples          []DictionaryExample `json:"examples"`
	EnrichmentError   *string             `json:"enrichment_error"`
}
