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
    openai_translation_model: str = "gpt-4o-mini"
    openai_asr_model: str = "whisper-1"
    asr_max_duration_seconds: int = 1800
    yt_dlp_cookies_file: str | None = None
    default_user_id: int = 1
    dev_access_token: str | None = None
    cache_ttl_seconds: int = 86400
    subtitle_batch_seconds: int = 120
    translation_batch_size: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
