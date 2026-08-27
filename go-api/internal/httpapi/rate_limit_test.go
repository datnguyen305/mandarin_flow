package httpapi

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/config"
)

type fakeRateLimitCounter struct {
	exceeded   bool
	retryAfter int64
	err        error
	called     int
	keys       []string
	limits     []interface{}
	seconds    int
}

func (counter *fakeRateLimitCounter) Count(_ context.Context, keys []string, limits []interface{}, seconds int) (bool, int64, error) {
	counter.called++
	counter.keys = keys
	counter.limits = limits
	counter.seconds = seconds
	return counter.exceeded, counter.retryAfter, counter.err
}

func TestRateLimitMiddlewareAllowsRequest(t *testing.T) {
	counter := &fakeRateLimitCounter{}
	called := false
	handler := rateLimitMiddlewareWithCounter(rateLimitTestConfig(), counter, http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		called = true
		writer.WriteHeader(http.StatusNoContent)
	}))

	request := httptest.NewRequest(http.MethodGet, "/api/videos", nil)
	request.RemoteAddr = "203.0.113.10:1234"
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)

	if response.Code != http.StatusNoContent || !called {
		t.Fatalf("expected request to pass, status=%d called=%v", response.Code, called)
	}
	if counter.called != 1 || len(counter.keys) != 1 || counter.seconds != 60 {
		t.Fatalf("unexpected counter call: calls=%d keys=%d seconds=%d", counter.called, len(counter.keys), counter.seconds)
	}
}

func TestRateLimitMiddlewareReturnsRetryAfter(t *testing.T) {
	counter := &fakeRateLimitCounter{exceeded: true, retryAfter: 17}
	handler := rateLimitMiddlewareWithCounter(rateLimitTestConfig(), counter, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		t.Fatal("next handler should not be called")
	}))

	request := httptest.NewRequest(http.MethodPost, "/api/videos/cookies", strings.NewReader("cookie"))
	request.RemoteAddr = "203.0.113.10:1234"
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)

	if response.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d", response.Code)
	}
	if response.Header().Get("Retry-After") != "17" {
		t.Fatalf("expected Retry-After 17, got %q", response.Header().Get("Retry-After"))
	}
	if !strings.Contains(response.Body.String(), "rate_limit_exceeded") {
		t.Fatalf("unexpected response: %s", response.Body.String())
	}
}

func TestRateLimitMiddlewareUsesIPAndGuestIdentity(t *testing.T) {
	counter := &fakeRateLimitCounter{}
	handler := rateLimitMiddlewareWithCounter(rateLimitTestConfig(), counter, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	request := httptest.NewRequest(http.MethodPost, "/api/videos/cookies", nil)
	request.RemoteAddr = "203.0.113.10:1234"
	request.AddCookie(&http.Cookie{Name: "mandarinflow_guest", Value: "guest-secret"})
	handler.ServeHTTP(httptest.NewRecorder(), request)

	if len(counter.keys) != 2 || len(counter.limits) != 2 {
		t.Fatalf("expected IP and guest counters, keys=%d limits=%d", len(counter.keys), len(counter.limits))
	}
	if counter.keys[0] == counter.keys[1] || !strings.Contains(counter.keys[0], "ip") || !strings.Contains(counter.keys[1], "guest") {
		t.Fatalf("unexpected identity keys: %v", counter.keys)
	}
	if strings.Contains(counter.keys[0], "203.0.113.10") || strings.Contains(counter.keys[1], "guest-secret") {
		t.Fatal("raw identity leaked into rate-limit key")
	}
}

func TestDisabledChatbotReturnsGoneWithoutCounting(t *testing.T) {
	counter := &fakeRateLimitCounter{}
	cfg := rateLimitTestConfig()
	cfg.ChatbotEnabled = false
	handler := rateLimitMiddlewareWithCounter(cfg, counter, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		t.Fatal("disabled chatbot should not reach handler")
	}))
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/api/agent/chat", nil))

	if response.Code != http.StatusGone || counter.called != 0 {
		t.Fatalf("expected 410 without counting, status=%d calls=%d", response.Code, counter.called)
	}
}

func TestRateLimitMiddlewareFailsClosedForExpensiveRedisError(t *testing.T) {
	counter := &fakeRateLimitCounter{err: context.DeadlineExceeded}
	handler := rateLimitMiddlewareWithCounter(rateLimitTestConfig(), counter, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		t.Fatal("expensive request should not pass when limiter is unavailable")
	}))
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/api/videos/cookies", nil))

	if response.Code != http.StatusServiceUnavailable || !strings.Contains(response.Body.String(), "rate_limit_unavailable") {
		t.Fatalf("expected 503 limiter error, status=%d body=%s", response.Code, response.Body.String())
	}
}

func TestRateLimitRuleClassification(t *testing.T) {
	cfg := rateLimitTestConfig()
	tests := []struct {
		method string
		path   string
		name   string
	}{
		{http.MethodGet, "/api/videos", "read"},
		{http.MethodPost, "/api/videos/cookies", "expensive"},
		{http.MethodPost, "/api/videos/process", "expensive"},
		{http.MethodPost, "/api/videos/v1/playback-position", "write"},
		{http.MethodPost, "/api/agent/chat", "chat"},
		{http.MethodPost, "/api/agent/integrations/telegram/webhook", "webhook"},
		{http.MethodPost, "/api/agent/requests/req_123/approve", "admin"},
	}
	for _, test := range tests {
		rule, ok := rateLimitRuleFor(httptest.NewRequest(test.method, test.path, nil), cfg)
		if !ok || rule.name != test.name {
			t.Errorf("%s %s: expected %s, got %q (applies=%v)", test.method, test.path, test.name, rule.name, ok)
		}
	}
}

func rateLimitTestConfig() config.Config {
	legacyURL, _ := url.Parse("http://backend:8000")
	return config.Config{
		LegacyBackendURL: legacyURL,
		FrontendURL:      "http://localhost:3000",
		GuestCookieName:  "mandarinflow_guest",
		ChatbotEnabled:   true,
		RateLimitEnabled: true,
		ReadLimit:        120,
		WriteLimit:       30,
		ExpensiveLimit:   5,
		AdminLimit:       10,
	}
}

func TestRateLimitKeyWindowIsStable(t *testing.T) {
	first := rateLimitKey("read", "ip", "identity", time.Minute)
	second := rateLimitKey("read", "ip", "identity", time.Minute)
	if first != second {
		t.Fatalf("expected same key within one window: %q != %q", first, second)
	}
}
