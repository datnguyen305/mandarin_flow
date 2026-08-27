package httpapi

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/config"
	"github.com/redis/go-redis/v9"
)

const rateLimitScript = `
local exceeded = 0
local retry_after = 0
for index, key in ipairs(KEYS) do
  local current = redis.call("INCR", key)
  if current == 1 then redis.call("EXPIRE", key, ARGV[1]) end
  local ttl = redis.call("TTL", key)
  if current > tonumber(ARGV[index + 1]) then exceeded = 1 end
  if ttl > retry_after then retry_after = ttl end
end
return {exceeded, retry_after}
`

type rateLimitRule struct {
	name    string
	limit   int
	window  time.Duration
	seconds int
}

type rateLimitCounter interface {
	Count(ctx context.Context, keys []string, limits []interface{}, seconds int) (bool, int64, error)
}

type redisRateLimitCounter struct {
	client *redis.Client
}

func (counter redisRateLimitCounter) Count(ctx context.Context, keys []string, limits []interface{}, seconds int) (bool, int64, error) {
	args := append([]interface{}{seconds}, limits...)
	result, err := counter.client.Eval(ctx, rateLimitScript, keys, args...).Result()
	if err != nil {
		return false, 0, err
	}
	values, ok := result.([]interface{})
	if !ok || len(values) != 2 {
		return false, 0, fmt.Errorf("unexpected rate limit response")
	}
	exceeded, exceededOK := toInt64(values[0])
	retryAfter, retryOK := toInt64(values[1])
	if !exceededOK || !retryOK {
		return false, 0, fmt.Errorf("invalid rate limit response")
	}
	return exceeded == 1, retryAfter, nil
}

func rateLimitMiddleware(cfg config.Config, client *redis.Client, next http.Handler) http.Handler {
	if client == nil {
		return next
	}
	return rateLimitMiddlewareWithCounter(cfg, redisRateLimitCounter{client: client}, next)
}

func rateLimitMiddlewareWithCounter(cfg config.Config, counter rateLimitCounter, next http.Handler) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if counter == nil || !cfg.RateLimitEnabled || request.Method == http.MethodOptions {
			next.ServeHTTP(writer, request)
			return
		}

		rule, applies := rateLimitRuleFor(request, cfg)
		if !applies {
			next.ServeHTTP(writer, request)
			return
		}
		if rule.name == "chat" && !cfg.ChatbotEnabled {
			writeError(writer, http.StatusGone, "chatbot_temporarily_disabled", "Chatbot hiện đang tạm ngưng.")
			return
		}

		keys := []string{rateLimitKey(rule.name, "ip", clientIdentity(request), rule.window)}
		limits := []interface{}{rule.limit}
		if guest := guestIdentity(request, cfg.GuestCookieName); guest != "" {
			keys = append(keys, rateLimitKey(rule.name, "guest", guest, rule.window))
			limits = append(limits, rule.limit)
		}

		exceeded, retryAfter, err := counter.Count(request.Context(), keys, limits, rule.seconds)
		if err != nil {
			// Fail closed for expensive/admin operations; a Redis outage must not
			// turn public API endpoints into an unbounded cost surface.
			if rule.name == "expensive" || rule.name == "admin" {
				writeError(writer, http.StatusServiceUnavailable, "rate_limit_unavailable", "Tạm thời không thể xử lý yêu cầu.")
				return
			}
			next.ServeHTTP(writer, request)
			return
		}

		if exceeded {
			if retryAfter < 1 {
				retryAfter = 1
			}
			writer.Header().Set("Retry-After", strconv.FormatInt(retryAfter, 10))
			writeError(writer, http.StatusTooManyRequests, "rate_limit_exceeded", "Bạn đang gửi quá nhiều yêu cầu. Vui lòng thử lại sau.")
			return
		}

		next.ServeHTTP(writer, request)
	})
}

func rateLimitRuleFor(request *http.Request, cfg config.Config) (rateLimitRule, bool) {
	path := request.URL.Path
	if path == "/health" || path == "/ready" {
		return rateLimitRule{}, false
	}
	if path == "/api/agent/chat" {
		if !cfg.ChatbotEnabled {
			return rateLimitRule{name: "chat", limit: 1, window: time.Minute, seconds: 60}, true
		}
		return rateLimitRule{name: "chat", limit: 10, window: time.Minute, seconds: 60}, true
	}
	if strings.HasPrefix(path, "/api/agent/integrations/telegram/") {
		return rateLimitRule{name: "webhook", limit: 30, window: time.Minute, seconds: 60}, true
	}
	if strings.HasPrefix(path, "/api/agent/requests/") || path == "/api/agent/requests" || path == "/api/dev/verify" {
		return rateLimitRule{name: "admin", limit: cfg.AdminLimit, window: time.Minute, seconds: 60}, true
	}
	if path == "/api/videos/cookies" || path == "/api/videos/process" || (request.Method == http.MethodPost && strings.Contains(path, "/batches/") && strings.HasSuffix(path, "/retry")) {
		return rateLimitRule{name: "expensive", limit: cfg.ExpensiveLimit, window: 10 * time.Minute, seconds: 600}, true
	}
	if request.Method == http.MethodGet {
		return rateLimitRule{name: "read", limit: cfg.ReadLimit, window: time.Minute, seconds: 60}, true
	}
	return rateLimitRule{name: "write", limit: cfg.WriteLimit, window: time.Minute, seconds: 60}, true
}

func rateLimitKey(group, kind, identity string, window time.Duration) string {
	windowID := time.Now().Unix() / int64(window/time.Second)
	return "ratelimit:v1:" + group + ":" + kind + ":" + identity + ":" + strconv.FormatInt(windowID, 10)
}

func clientIdentity(request *http.Request) string {
	value := request.Header.Get("X-Forwarded-For")
	if index := strings.IndexByte(value, ','); index >= 0 {
		value = value[:index]
	}
	if value == "" {
		value = request.RemoteAddr
		if host, _, err := net.SplitHostPort(value); err == nil {
			value = host
		}
	}
	return hashRateLimitIdentity(strings.TrimSpace(value))
}

func guestIdentity(request *http.Request, cookieName string) string {
	cookie, err := request.Cookie(cookieName)
	if err != nil || cookie.Value == "" {
		return ""
	}
	return hashRateLimitIdentity(cookie.Value)
}

func hashRateLimitIdentity(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func toInt64(value interface{}) (int64, bool) {
	switch typed := value.(type) {
	case int64:
		return typed, true
	case int:
		return int64(typed), true
	case string:
		parsed, err := strconv.ParseInt(typed, 10, 64)
		return parsed, err == nil
	default:
		return 0, false
	}
}
