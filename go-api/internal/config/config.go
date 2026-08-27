package config

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	ListenAddress    string
	LegacyBackendURL *url.URL
	FrontendURL      string
	DatabaseURL      string
	RedisURL         string
	Environment      string
	GuestCookieName  string
	GuestSessionDays int
	DevAccessToken   string
	CookiesFile      string
	ChatbotEnabled   bool
	RateLimitEnabled bool
	ReadLimit        int
	WriteLimit       int
	ExpensiveLimit   int
	AdminLimit       int
}

func Load() (Config, error) {
	legacyURL, err := url.Parse(envOrDefault("LEGACY_BACKEND_URL", "http://backend:8000"))
	if err != nil || legacyURL.Scheme == "" || legacyURL.Host == "" {
		return Config{}, fmt.Errorf("LEGACY_BACKEND_URL must be an absolute URL")
	}

	guestDays, err := strconv.Atoi(envOrDefault("GUEST_SESSION_DAYS", "365"))
	if err != nil || guestDays < 1 {
		return Config{}, fmt.Errorf("GUEST_SESSION_DAYS must be a positive integer")
	}

	return Config{
		ListenAddress:    envOrDefault("LISTEN_ADDRESS", ":8080"),
		LegacyBackendURL: legacyURL,
		FrontendURL:      envOrDefault("FRONTEND_URL", "http://localhost:3000"),
		DatabaseURL:      normalizeDatabaseURL(envOrDefault("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/youtube_language_learning")),
		RedisURL:         envOrDefault("REDIS_URL", "redis://redis:6379/0"),
		Environment:      envOrDefault("ENVIRONMENT", "development"),
		GuestCookieName:  envOrDefault("GUEST_COOKIE_NAME", "mandarinflow_guest"),
		GuestSessionDays: guestDays,
		DevAccessToken:   os.Getenv("DEV_ACCESS_TOKEN"),
		CookiesFile:      envOrDefault("YT_DLP_COOKIES_FILE", "/app/cookies/cookies.txt"),
		ChatbotEnabled:   boolEnvOrDefault("CHATBOT_ENABLED", true),
		RateLimitEnabled: boolEnvOrDefault("RATE_LIMIT_ENABLED", true),
		ReadLimit:        intEnvOrDefault("RATE_LIMIT_READ_PER_MINUTE", 120),
		WriteLimit:       intEnvOrDefault("RATE_LIMIT_WRITE_PER_MINUTE", 30),
		ExpensiveLimit:   intEnvOrDefault("RATE_LIMIT_EXPENSIVE_PER_WINDOW", 5),
		AdminLimit:       intEnvOrDefault("RATE_LIMIT_ADMIN_PER_MINUTE", 10),
	}, nil
}

func normalizeDatabaseURL(value string) string {
	return strings.Replace(value, "postgresql+asyncpg://", "postgresql://", 1)
}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func boolEnvOrDefault(name string, fallback bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(name)))
	if value == "" {
		return fallback
	}
	return value == "1" || value == "true" || value == "yes" || value == "on"
}

func intEnvOrDefault(name string, fallback int) int {
	value, err := strconv.Atoi(os.Getenv(name))
	if err != nil || value < 1 {
		return fallback
	}
	return value
}
