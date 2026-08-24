from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MandarinFlow API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/youtube_language_learning"
    redis_url: str = "redis://redis:6379/0"
    frontend_url: str = "http://localhost:3000"
    translation_provider: str = "local"
    translation_api_key: str | None = None
    dictionary_provider: str = "cvdict"
    cvdict_path: str = "app/data/CVDICT.u8"
    asr_provider: str = "disabled"
    openai_api_key: str | None = None
    openai_translation_api_key: str | None = None
    openai_asr_api_key: str | None = None
    openai_chat_api_key: str | None = None
    openai_translation_model: str = "gpt-4o-mini"
    openai_chat_model: str = "gpt-4o-mini"
    openai_asr_model: str = "whisper-1"
    asr_max_duration_seconds: int = 1800
    asr_chunk_duration_seconds: int = 300
    asr_connect_timeout_seconds: float = 15.0
    asr_read_timeout_seconds: float = 180.0
    asr_write_timeout_seconds: float = 180.0
    asr_pool_timeout_seconds: float = 15.0
    asr_max_attempts_per_chunk: int = 3
    asr_retry_backoff_seconds: float = 2.0
    yt_dlp_cookies_file: str | None = None
    yt_dlp_js_runtime_path: str | None = "/root/.deno/bin/deno"
    yt_dlp_remote_components: str | None = "ejs:github"
    yt_dlp_player_client: str | None = None
    yt_dlp_max_attempts: int = 2
    yt_dlp_retry_backoff_seconds: float = 1.5
    yt_dlp_socket_timeout: int = 30
    youtube_metadata_backfill_enabled: bool = True
    youtube_metadata_backfill_batch_size: int = 100
    youtube_metadata_backfill_concurrency: int = 2
    guest_cookie_name: str = "mandarinflow_guest"
    guest_session_days: int = 365
    dev_access_token: str | None = None
    cache_ttl_seconds: int = 86400
    subtitle_batch_seconds: int = 120
    translation_batch_size: int = 30
    subtitle_nlp_provider: str = "openai"
    openai_nlp_model: str = "gpt-4o-mini"
    video_topic_classifier_provider: str = "openai"
    openai_topic_model: str = "gpt-4o-mini"
    telegram_bot_token: str | None = None
    telegram_admin_chat_id: str | None = None
    telegram_allowed_user_id: str | None = None
    telegram_webhook_secret: str | None = None
    telegram_connect_timeout_seconds: float = 15.0
    telegram_read_timeout_seconds: float = 30.0
    telegram_write_timeout_seconds: float = 30.0
    telegram_pool_timeout_seconds: float = 15.0
    telegram_max_attempts: int = 3
    telegram_retry_backoff_seconds: float = 0.5
    agent_request_expiry_hours: int = 24
    chatbot_video_request_limit: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
