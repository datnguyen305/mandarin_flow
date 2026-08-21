package httpapi

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/config"
)

func TestHealth(t *testing.T) {
	handler := testHandler(t, "http://127.0.0.1:1")
	request := httptest.NewRequest(http.MethodGet, "/health", nil)
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", response.Code)
	}
	var payload map[string]string
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	if payload["service"] != "go-api" {
		t.Fatalf("expected go-api service, got %q", payload["service"])
	}
}

func TestProxyPreservesHeadersCookiesAndBody(t *testing.T) {
	transport := roundTripperFunc(func(request *http.Request) (*http.Response, error) {
		if request.Header.Get("X-Dev-Token") != "dev-secret" {
			t.Fatal("X-Dev-Token was not proxied")
		}
		cookie, err := request.Cookie("mandarinflow_guest")
		if err != nil || cookie.Value != "guest-token" {
			t.Fatal("guest cookie was not proxied")
		}
		body, _ := io.ReadAll(request.Body)
		if string(body) != `{"word":"字幕"}` {
			t.Fatalf("unexpected request body: %s", body)
		}
		return &http.Response{
			StatusCode: http.StatusAccepted,
			Header: http.Header{
				"Content-Type": {"application/json"},
				"Set-Cookie":   {"mandarinflow_guest=renewed; Path=/; HttpOnly"},
			},
			Body: io.NopCloser(strings.NewReader(`{"status":"saved"}`)),
		}, nil
	})

	legacyURL, err := url.Parse("http://legacy-backend:8000")
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := newHandler(config.Config{LegacyBackendURL: legacyURL, FrontendURL: "https://mandarinflow.online"}, logger, Dependencies{}, transport)
	request := httptest.NewRequest(http.MethodPost, "/api/vocabulary", strings.NewReader(`{"word":"字幕"}`))
	request.Header.Set("X-Dev-Token", "dev-secret")
	request.AddCookie(&http.Cookie{Name: "mandarinflow_guest", Value: "guest-token"})
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", response.Code)
	}
	if !strings.Contains(response.Header().Get("Set-Cookie"), "renewed") {
		t.Fatal("response cookie was not preserved")
	}
	if response.Body.String() != `{"status":"saved"}` {
		t.Fatalf("unexpected response body: %s", response.Body.String())
	}
}

type roundTripperFunc func(*http.Request) (*http.Response, error)

func (fn roundTripperFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return fn(request)
}

func TestCORSAllowsConfiguredFrontend(t *testing.T) {
	handler := testHandler(t, "http://127.0.0.1:1")
	request := httptest.NewRequest(http.MethodOptions, "/api/videos", nil)
	request.Header.Set("Origin", "https://mandarinflow.online")
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", response.Code)
	}
	if response.Header().Get("Access-Control-Allow-Origin") != "https://mandarinflow.online" {
		t.Fatal("configured frontend origin was not allowed")
	}
}

func testHandler(t *testing.T, legacy string) http.Handler {
	t.Helper()
	legacyURL, err := url.Parse(legacy)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	return NewHandler(config.Config{LegacyBackendURL: legacyURL, FrontendURL: "https://mandarinflow.online"}, logger)
}
