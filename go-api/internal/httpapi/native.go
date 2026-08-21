package httpapi

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log/slog"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/config"
	"github.com/datnguyen305/mandarin-flow/go-api/internal/domain"
	"github.com/datnguyen305/mandarin-flow/go-api/internal/store"
	"github.com/redis/go-redis/v9"
)

type Dependencies struct {
	Store *store.Postgres
	Redis *redis.Client
}

type nativeAPI struct {
	cfg    config.Config
	deps   Dependencies
	logger *slog.Logger
}

func (api *nativeAPI) register(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/videos", api.listVideos)
	mux.HandleFunc("GET /api/videos/progress", api.listProgress)
	mux.HandleFunc("POST /api/videos/cookies", api.uploadCookies)
	mux.HandleFunc("GET /api/videos/{videoID}/subtitles/raw", api.getSubtitles(true))
	mux.HandleFunc("GET /api/videos/{videoID}/subtitles", api.getSubtitles(false))
	mux.HandleFunc("GET /api/videos/{videoID}", api.getVideo)
	mux.HandleFunc("DELETE /api/videos/{videoID}", api.deleteVideo)
	mux.HandleFunc("POST /api/vocabulary", api.saveVocabulary)
	mux.HandleFunc("GET /api/vocabulary", api.listVocabulary)
	mux.HandleFunc("DELETE /api/vocabulary/{vocabularyID}", api.deleteVocabulary)
}

func (api *nativeAPI) listVideos(writer http.ResponseWriter, request *http.Request) {
	limit := 50
	if rawLimit := request.URL.Query().Get("limit"); rawLimit != "" {
		parsed, err := strconv.Atoi(rawLimit)
		if err != nil {
			writeError(writer, http.StatusUnprocessableEntity, "validation_error", "Invalid limit")
			return
		}
		limit = parsed
	}
	if limit < 1 {
		limit = 1
	}
	if limit > 100 {
		limit = 100
	}
	items, err := api.deps.Store.ListVideos(request.Context(), limit, api.hasDevAccess(request))
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusOK, items)
}

func (api *nativeAPI) getVideo(writer http.ResponseWriter, request *http.Request) {
	video, err := api.deps.Store.GetVideo(request.Context(), request.PathValue("videoID"))
	if errors.Is(err, store.ErrNotFound) {
		writeError(writer, http.StatusNotFound, "video_unavailable", "Video not found")
		return
	}
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusOK, video)
}

func (api *nativeAPI) deleteVideo(writer http.ResponseWriter, request *http.Request) {
	if !api.requireDevAccess(writer, request) {
		return
	}
	videoID := request.PathValue("videoID")
	deleted, err := api.deps.Store.DeleteVideo(request.Context(), videoID)
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}
	if !deleted {
		writeError(writer, http.StatusNotFound, "video_unavailable", "Video not found")
		return
	}
	if api.deps.Redis != nil {
		if err := api.deps.Redis.Del(request.Context(), "video:"+videoID+":subtitles:zh-vi").Err(); err != nil {
			api.logger.Warn("subtitle cache delete failed", "video_id", videoID, "error", err)
		}
	}
	writer.WriteHeader(http.StatusNoContent)
}

func (api *nativeAPI) getSubtitles(raw bool) http.HandlerFunc {
	return func(writer http.ResponseWriter, request *http.Request) {
		result, err := api.deps.Store.GetSubtitles(request.Context(), request.PathValue("videoID"))
		if errors.Is(err, store.ErrNotFound) {
			message := "Processed subtitles are unavailable. Process the video first."
			if raw {
				message = "Raw subtitles are unavailable. Start processing the video first."
			}
			writeError(writer, http.StatusNotFound, "subtitles_unavailable", message)
			return
		}
		if err != nil {
			api.databaseError(writer, request, err)
			return
		}
		writeJSON(writer, http.StatusOK, result)
	}
}

func (api *nativeAPI) listProgress(writer http.ResponseWriter, request *http.Request) {
	guest, ok := api.guest(writer, request)
	if !ok {
		return
	}
	items, err := api.deps.Store.ListProgress(request.Context(), guest.ID)
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusOK, items)
}

func (api *nativeAPI) updateProgress(writer http.ResponseWriter, request *http.Request) {
	guest, ok := api.guest(writer, request)
	if !ok {
		return
	}
	var payload struct {
		CurrentTime float64 `json:"current_time"`
	}
	if !decodeJSON(writer, request, &payload) {
		return
	}
	if math.IsNaN(payload.CurrentTime) || math.IsInf(payload.CurrentTime, 0) {
		writeError(writer, http.StatusUnprocessableEntity, "validation_error", "Invalid current_time")
		return
	}
	if payload.CurrentTime < 0 {
		payload.CurrentTime = 0
	}
	if err := api.deps.Store.UpdateProgress(request.Context(), guest.ID, request.PathValue("videoID"), payload.CurrentTime); err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusAccepted, map[string]string{"status": "accepted"})
}

func (api *nativeAPI) saveVocabulary(writer http.ResponseWriter, request *http.Request) {
	guest, ok := api.guest(writer, request)
	if !ok {
		return
	}
	var input domain.SaveVocabularyInput
	if !decodeJSON(writer, request, &input) {
		return
	}
	if strings.TrimSpace(input.Word) == "" || input.YouTubeVideoID == "" || input.SubtitleID < 1 || math.IsNaN(input.Timestamp) || math.IsInf(input.Timestamp, 0) {
		writeError(writer, http.StatusUnprocessableEntity, "validation_error", "Invalid vocabulary payload")
		return
	}
	id, err := api.deps.Store.SaveVocabulary(request.Context(), guest.ID, input)
	if errors.Is(err, store.ErrNotFound) {
		writeError(writer, http.StatusInternalServerError, "internal_error", "Video or subtitle not found")
		return
	}
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusOK, map[string]any{"id": id, "status": "saved"})
}

func (api *nativeAPI) listVocabulary(writer http.ResponseWriter, request *http.Request) {
	guest, ok := api.guest(writer, request)
	if !ok {
		return
	}
	items, err := api.deps.Store.ListVocabulary(request.Context(), guest.ID)
	if err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusOK, items)
}

func (api *nativeAPI) deleteVocabulary(writer http.ResponseWriter, request *http.Request) {
	guest, ok := api.guest(writer, request)
	if !ok {
		return
	}
	id, err := strconv.ParseInt(request.PathValue("vocabularyID"), 10, 64)
	if err != nil {
		writeError(writer, http.StatusUnprocessableEntity, "validation_error", "Invalid vocabulary id")
		return
	}
	if err := api.deps.Store.DeleteVocabulary(request.Context(), guest.ID, id); err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writer.WriteHeader(http.StatusNoContent)
}

func (api *nativeAPI) uploadCookies(writer http.ResponseWriter, request *http.Request) {
	if !api.requireDevAccess(writer, request) {
		return
	}
	var payload struct {
		Content string `json:"content"`
	}
	if !decodeJSON(writer, request, &payload) {
		return
	}
	content := strings.TrimSpace(payload.Content)
	if content == "" {
		writeError(writer, http.StatusNotFound, "subtitles_unavailable", "Cookies content is empty.")
		return
	}
	if err := os.MkdirAll(filepath.Dir(api.cfg.CookiesFile), 0o755); err != nil {
		api.databaseError(writer, request, err)
		return
	}
	if err := os.WriteFile(api.cfg.CookiesFile, []byte(content+"\n"), 0o600); err != nil {
		api.databaseError(writer, request, err)
		return
	}
	writeJSON(writer, http.StatusAccepted, map[string]string{"status": "saved", "path": api.cfg.CookiesFile})
}

func (api *nativeAPI) guest(writer http.ResponseWriter, request *http.Request) (*domain.Guest, bool) {
	now := time.Now().UTC()
	if cookie, err := request.Cookie(api.cfg.GuestCookieName); err == nil && cookie.Value != "" {
		guest, findErr := api.deps.Store.FindGuest(request.Context(), hashToken(cookie.Value), now)
		if findErr == nil {
			if now.Sub(guest.LastSeenAt) > 24*time.Hour {
				_ = api.deps.Store.TouchGuest(request.Context(), guest.ID, now)
			}
			return guest, true
		}
		if !errors.Is(findErr, store.ErrNotFound) {
			api.databaseError(writer, request, findErr)
			return nil, false
		}
	}
	rawToken, err := randomToken(32)
	if err != nil {
		api.databaseError(writer, request, err)
		return nil, false
	}
	id, err := uuidV4()
	if err != nil {
		api.databaseError(writer, request, err)
		return nil, false
	}
	expiresAt := now.Add(time.Duration(api.cfg.GuestSessionDays) * 24 * time.Hour)
	guest, err := api.deps.Store.CreateGuest(request.Context(), id, hashToken(rawToken), expiresAt)
	if err != nil {
		api.databaseError(writer, request, err)
		return nil, false
	}
	http.SetCookie(writer, &http.Cookie{Name: api.cfg.GuestCookieName, Value: rawToken, Path: "/", MaxAge: api.cfg.GuestSessionDays * 86400, Expires: expiresAt, HttpOnly: true, Secure: api.cfg.Environment == "production", SameSite: http.SameSiteLaxMode})
	return guest, true
}

func (api *nativeAPI) hasDevAccess(request *http.Request) bool {
	provided := request.Header.Get("X-Dev-Token")
	if api.cfg.DevAccessToken == "" || len(provided) != len(api.cfg.DevAccessToken) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(provided), []byte(api.cfg.DevAccessToken)) == 1
}

func (api *nativeAPI) requireDevAccess(writer http.ResponseWriter, request *http.Request) bool {
	if api.hasDevAccess(request) {
		return true
	}
	writeJSON(writer, http.StatusForbidden, map[string]string{"detail": "Dev access is required."})
	return false
}

func (api *nativeAPI) databaseError(writer http.ResponseWriter, request *http.Request, err error) {
	api.logger.Error("native api request failed", "path", request.URL.Path, "error", err)
	writeError(writer, http.StatusInternalServerError, "database_failure", "Database request failed")
}

func decodeJSON(writer http.ResponseWriter, request *http.Request, target any) bool {
	decoder := json.NewDecoder(http.MaxBytesReader(writer, request.Body, 1<<20))
	if err := decoder.Decode(target); err != nil {
		writeError(writer, http.StatusUnprocessableEntity, "validation_error", "Invalid request body")
		return false
	}
	return true
}

func writeError(writer http.ResponseWriter, status int, code, message string) {
	writeJSON(writer, status, map[string]any{"error": map[string]string{"code": code, "message": message}})
}
func hashToken(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}
func randomToken(size int) (string, error) {
	buffer := make([]byte, size)
	if _, err := rand.Read(buffer); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buffer), nil
}
func uuidV4() (string, error) {
	var value [16]byte
	if _, err := rand.Read(value[:]); err != nil {
		return "", err
	}
	value[6] = (value[6] & 0x0f) | 0x40
	value[8] = (value[8] & 0x3f) | 0x80
	encoded := hex.EncodeToString(value[:])
	return encoded[0:8] + "-" + encoded[8:12] + "-" + encoded[12:16] + "-" + encoded[16:20] + "-" + encoded[20:32], nil
}

func pingRedis(ctx context.Context, client *redis.Client) error {
	if client == nil {
		return nil
	}
	return client.Ping(ctx).Err()
}
