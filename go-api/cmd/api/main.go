package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/datnguyen305/mandarin-flow/go-api/internal/config"
	"github.com/datnguyen305/mandarin-flow/go-api/internal/httpapi"
	"github.com/datnguyen305/mandarin-flow/go-api/internal/store"
	"github.com/redis/go-redis/v9"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		slog.Error("invalid configuration", "error", err)
		os.Exit(1)
	}

	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	startupCtx, cancelStartup := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancelStartup()
	database, err := store.NewPostgres(startupCtx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("database connection failed", "error", err)
		os.Exit(1)
	}
	defer database.Close()
	redisOptions, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		logger.Error("invalid redis url", "error", err)
		os.Exit(1)
	}
	redisClient := redis.NewClient(redisOptions)
	defer redisClient.Close()
	if err := redisClient.Ping(startupCtx).Err(); err != nil {
		logger.Warn("redis unavailable; cache invalidation will degrade", "error", err)
	}

	server := &http.Server{
		Addr:              cfg.ListenAddress,
		Handler:           httpapi.NewHandlerWithDependencies(cfg, logger, httpapi.Dependencies{Store: database, Redis: redisClient}),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	errCh := make(chan error, 1)
	go func() {
		logger.Info("go api listening", "address", cfg.ListenAddress, "legacy_backend", cfg.LegacyBackendURL.String())
		errCh <- server.ListenAndServe()
	}()

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			logger.Error("graceful shutdown failed", "error", err)
		}
	case err := <-errCh:
		if err != nil && err != http.ErrServerClosed {
			logger.Error("http server stopped", "error", err)
			os.Exit(1)
		}
	}
}
