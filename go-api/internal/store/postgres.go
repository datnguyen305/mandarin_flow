package store

import (
	"context"
	"errors"
	"time"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/domain"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrNotFound = errors.New("not found")

type Postgres struct {
	pool *pgxpool.Pool
}

func NewPostgres(ctx context.Context, databaseURL string) (*Postgres, error) {
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &Postgres{pool: pool}, nil
}

func (db *Postgres) Close()                         { db.pool.Close() }
func (db *Postgres) Ping(ctx context.Context) error { return db.pool.Ping(ctx) }

func (db *Postgres) FindGuest(ctx context.Context, tokenHash string, now time.Time) (*domain.Guest, error) {
	guest := domain.Guest{}
	err := db.pool.QueryRow(ctx, `SELECT id::text, last_seen_at FROM guest_sessions WHERE token_hash=$1 AND expires_at>$2`, tokenHash, now).Scan(&guest.ID, &guest.LastSeenAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &guest, err
}

func (db *Postgres) CreateGuest(ctx context.Context, id, tokenHash string, expiresAt time.Time) (*domain.Guest, error) {
	guest := domain.Guest{ID: id}
	err := db.pool.QueryRow(ctx, `INSERT INTO guest_sessions (id, token_hash, expires_at) VALUES ($1::uuid,$2,$3) RETURNING last_seen_at`, id, tokenHash, expiresAt).Scan(&guest.LastSeenAt)
	return &guest, err
}

func (db *Postgres) TouchGuest(ctx context.Context, id string, now time.Time) error {
	_, err := db.pool.Exec(ctx, `UPDATE guest_sessions SET last_seen_at=$2 WHERE id=$1::uuid`, id, now)
	return err
}

func (db *Postgres) ListVideos(ctx context.Context, limit int, includeUnpublished bool) ([]domain.Video, error) {
	query := `SELECT id,youtube_video_id,title,url,thumbnail_url,language,processing_status,created_at FROM videos`
	args := []any{}
	if !includeUnpublished {
		query += ` WHERE processing_status='completed'`
	}
	query += ` ORDER BY created_at DESC,id DESC LIMIT $1`
	args = append(args, limit)
	rows, err := db.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []domain.Video{}
	for rows.Next() {
		var item domain.Video
		if err := rows.Scan(&item.ID, &item.YouTubeVideoID, &item.Title, &item.URL, &item.ThumbnailURL, &item.Language, &item.ProcessingStatus, &item.CreatedAt); err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, rows.Err()
}

func (db *Postgres) GetVideo(ctx context.Context, videoID string) (*domain.Video, error) {
	var item domain.Video
	err := db.pool.QueryRow(ctx, `SELECT id,youtube_video_id,title,url,thumbnail_url,language,processing_status,created_at FROM videos WHERE youtube_video_id=$1`, videoID).Scan(&item.ID, &item.YouTubeVideoID, &item.Title, &item.URL, &item.ThumbnailURL, &item.Language, &item.ProcessingStatus, &item.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &item, err
}

func (db *Postgres) DeleteVideo(ctx context.Context, videoID string) (bool, error) {
	result, err := db.pool.Exec(ctx, `DELETE FROM videos WHERE youtube_video_id=$1`, videoID)
	return result.RowsAffected() > 0, err
}

func (db *Postgres) GetSubtitles(ctx context.Context, videoID string) (*domain.SubtitleResponse, error) {
	video, err := db.GetVideo(ctx, videoID)
	if err != nil {
		return nil, err
	}
	rows, err := db.pool.Query(ctx, `SELECT s.id,s.start_time,s.end_time,s.text,s.translated_text,s.processing_status,t.text,t.pinyin,t.meaning,t.start_index,t.end_index FROM subtitles s LEFT JOIN subtitle_tokens t ON t.subtitle_id=s.id WHERE s.video_id=$1 ORDER BY s.sequence_number,t.start_index`, video.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	response := &domain.SubtitleResponse{VideoID: video.YouTubeVideoID, Title: video.Title, Subtitles: []domain.SubtitleLine{}}
	indexes := map[int64]int{}
	for rows.Next() {
		var subtitleID int64
		var start, end float64
		var text, status string
		var translation *string
		var tokenText, pinyin, meaning *string
		var startIndex, endIndex *int
		if err := rows.Scan(&subtitleID, &start, &end, &text, &translation, &status, &tokenText, &pinyin, &meaning, &startIndex, &endIndex); err != nil {
			return nil, err
		}
		position, exists := indexes[subtitleID]
		if !exists {
			position = len(response.Subtitles)
			indexes[subtitleID] = position
			response.Subtitles = append(response.Subtitles, domain.SubtitleLine{ID: subtitleID, Start: start, End: end, Text: text, Translation: translation, ProcessingStatus: status, Tokens: []domain.SubtitleToken{}})
		}
		if tokenText != nil {
			response.Subtitles[position].Tokens = append(response.Subtitles[position].Tokens, domain.SubtitleToken{Text: *tokenText, Pinyin: pinyin, Meaning: meaning, StartIndex: startIndex, EndIndex: endIndex})
		}
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(response.Subtitles) == 0 {
		return nil, ErrNotFound
	}
	return response, nil
}

func (db *Postgres) ListProgress(ctx context.Context, guestID string) ([]domain.VideoProgress, error) {
	rows, err := db.pool.Query(ctx, `SELECT v.youtube_video_id,p.current_time,p.completed,p.last_watched_at FROM guest_video_progress p JOIN videos v ON v.id=p.video_id WHERE p.guest_id=$1::uuid ORDER BY p.last_watched_at DESC`, guestID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []domain.VideoProgress{}
	for rows.Next() {
		var item domain.VideoProgress
		if err := rows.Scan(&item.YouTubeVideoID, &item.CurrentTime, &item.Completed, &item.LastWatchedAt); err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, rows.Err()
}

func (db *Postgres) UpdateProgress(ctx context.Context, guestID, videoID string, currentTime float64) error {
	_, err := db.pool.Exec(ctx, `INSERT INTO guest_video_progress (guest_id,video_id,current_time) SELECT $1::uuid,id,$3 FROM videos WHERE youtube_video_id=$2 ON CONFLICT ON CONSTRAINT uq_guest_video_progress_guest_video DO UPDATE SET current_time=EXCLUDED.current_time,last_watched_at=now()`, guestID, videoID, currentTime)
	return err
}

func (db *Postgres) SaveVocabulary(ctx context.Context, guestID string, input domain.SaveVocabularyInput) (int64, error) {
	var id int64
	err := db.pool.QueryRow(ctx, `INSERT INTO saved_vocabulary (guest_id,word,pinyin,meaning,video_id,subtitle_id,timestamp) SELECT $1::uuid,$2,$3,$4,v.id,s.id,$7 FROM videos v JOIN subtitles s ON s.id=$6 AND s.video_id=v.id WHERE v.youtube_video_id=$5 RETURNING id`, guestID, input.Word, input.Pinyin, input.Meaning, input.YouTubeVideoID, input.SubtitleID, input.Timestamp).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, ErrNotFound
	}
	return id, err
}

func (db *Postgres) ListVocabulary(ctx context.Context, guestID string) ([]domain.SavedVocabulary, error) {
	rows, err := db.pool.Query(ctx, `SELECT sv.id,sv.word,sv.pinyin,sv.meaning,v.youtube_video_id,v.title,s.text,sv.timestamp,sv.created_at FROM saved_vocabulary sv JOIN videos v ON v.id=sv.video_id JOIN subtitles s ON s.id=sv.subtitle_id WHERE sv.guest_id=$1::uuid ORDER BY sv.created_at DESC`, guestID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []domain.SavedVocabulary{}
	for rows.Next() {
		var item domain.SavedVocabulary
		if err := rows.Scan(&item.ID, &item.Word, &item.Pinyin, &item.Meaning, &item.YouTubeVideoID, &item.VideoTitle, &item.SubtitleSentence, &item.Timestamp, &item.CreatedAt); err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, rows.Err()
}

func (db *Postgres) DeleteVocabulary(ctx context.Context, guestID string, id int64) error {
	_, err := db.pool.Exec(ctx, `DELETE FROM saved_vocabulary WHERE id=$1 AND guest_id=$2::uuid`, id, guestID)
	return err
}
