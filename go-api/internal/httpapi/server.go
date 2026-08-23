package httpapi

import (
	"crypto/rand"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/config"
)

func NewHandler(cfg config.Config, logger *slog.Logger) http.Handler {
	return newHandler(cfg, logger, Dependencies{}, nil)
}

func NewHandlerWithDependencies(cfg config.Config, logger *slog.Logger, deps Dependencies) http.Handler {
	return newHandler(cfg, logger, deps, nil)
}

func newHandler(cfg config.Config, logger *slog.Logger, deps Dependencies, transport http.RoundTripper) http.Handler {
	proxy := newLegacyProxy(cfg.LegacyBackendURL, logger)
	if transport != nil {
		proxy.Transport = transport
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", jsonHandler(http.StatusOK, map[string]string{"status": "ok", "service": "go-api"}))
	mux.HandleFunc("GET /ready", readinessHandler(cfg.LegacyBackendURL, deps))
	native := &nativeAPI{cfg: cfg, deps: deps, logger: logger}
	mux.HandleFunc("GET /api/dev/verify", native.verifyDevAccess)
	if deps.Store != nil {
		native.register(mux)
	}
	mux.Handle("/api/", proxy)

	return recoverer(logger)(requestID(requestLogger(logger)(cors(cfg.FrontendURL)(mux))))
}

func newLegacyProxy(target *url.URL, logger *slog.Logger) *httputil.ReverseProxy {
	proxy := httputil.NewSingleHostReverseProxy(target)
	originalDirector := proxy.Director
	proxy.Director = func(request *http.Request) {
		originalHost := request.Host
		originalDirector(request)
		request.Header.Set("X-Forwarded-Host", originalHost)
		request.Header.Set("X-Forwarded-Proto", forwardedProto(request))
	}
	proxy.ErrorHandler = func(writer http.ResponseWriter, request *http.Request, err error) {
		logger.Error("legacy backend request failed", "path", request.URL.Path, "error", err)
		writeJSON(writer, http.StatusBadGateway, map[string]any{
			"error": map[string]string{
				"code":    "upstream_unavailable",
				"message": "Backend service is unavailable.",
			},
		})
	}
	return proxy
}

func readinessHandler(legacyURL *url.URL, deps Dependencies) http.HandlerFunc {
	client := &http.Client{Timeout: 2 * time.Second}
	return func(writer http.ResponseWriter, request *http.Request) {
		if deps.Store != nil {
			if err := deps.Store.Ping(request.Context()); err != nil {
				writeJSON(writer, http.StatusServiceUnavailable, map[string]string{"status": "not_ready", "database": "unavailable"})
				return
			}
		}
		healthURL := legacyURL.ResolveReference(&url.URL{Path: "/health"})
		response, err := client.Get(healthURL.String())
		if err != nil || response.StatusCode != http.StatusOK {
			if response != nil {
				response.Body.Close()
			}
			writeJSON(writer, http.StatusServiceUnavailable, map[string]string{"status": "not_ready"})
			return
		}
		response.Body.Close()
		writeJSON(writer, http.StatusOK, map[string]string{"status": "ready"})
	}
}

func cors(frontendURL string) func(http.Handler) http.Handler {
	allowedOrigins := map[string]struct{}{
		strings.TrimRight(frontendURL, "/"): {},
		"http://localhost:3000":             {},
		"http://127.0.0.1:3000":             {},
	}
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			origin := request.Header.Get("Origin")
			if _, allowed := allowedOrigins[origin]; allowed {
				writer.Header().Set("Access-Control-Allow-Origin", origin)
				writer.Header().Set("Access-Control-Allow-Credentials", "true")
				writer.Header().Set("Vary", "Origin")
			}
			writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Dev-Token, Last-Event-ID")
			writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
			if request.Method == http.MethodOptions {
				writer.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(writer, request)
		})
	}
}

func requestLogger(logger *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			startedAt := time.Now()
			next.ServeHTTP(writer, request)
			logger.Info("http request", "method", request.Method, "path", request.URL.Path, "duration_ms", time.Since(startedAt).Milliseconds())
		})
	}
}

func requestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		id := request.Header.Get("X-Request-ID")
		if id == "" {
			var random [8]byte
			if _, err := rand.Read(random[:]); err == nil {
				id = fmt.Sprintf("%x", random[:])
			}
		}
		if id != "" {
			writer.Header().Set("X-Request-ID", id)
			request.Header.Set("X-Request-ID", id)
		}
		next.ServeHTTP(writer, request)
	})
}

func recoverer(logger *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			defer func() {
				if recovered := recover(); recovered != nil {
					if recovered == http.ErrAbortHandler {
						panic(recovered)
					}
					logger.Error("panic recovered", "path", request.URL.Path, "error", recovered)
					writeJSON(writer, http.StatusInternalServerError, map[string]any{
						"error": map[string]string{"code": "internal_error", "message": "Internal server error."},
					})
				}
			}()
			next.ServeHTTP(writer, request)
		})
	}
}

func jsonHandler(status int, payload any) http.HandlerFunc {
	return func(writer http.ResponseWriter, _ *http.Request) {
		writeJSON(writer, status, payload)
	}
}

func writeJSON(writer http.ResponseWriter, status int, payload any) {
	writer.Header().Set("Content-Type", "application/json")
	writer.WriteHeader(status)
	_ = json.NewEncoder(writer).Encode(payload)
}

func forwardedProto(request *http.Request) string {
	if value := request.Header.Get("X-Forwarded-Proto"); value != "" {
		return value
	}
	if request.TLS != nil {
		return "https"
	}
	return "http"
}
