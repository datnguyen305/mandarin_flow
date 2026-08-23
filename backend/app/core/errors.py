class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidYouTubeUrlError(AppError):
    status_code = 400
    code = "invalid_youtube_url"


class VideoUnavailableError(AppError):
    status_code = 404
    code = "video_unavailable"


class SubtitlesUnavailableError(AppError):
    status_code = 404
    code = "subtitles_unavailable"


class UnsupportedLanguageError(AppError):
    status_code = 400
    code = "unsupported_language"


class TranslationProviderError(AppError):
    status_code = 502
    code = "translation_provider_failure"


class ASRProviderError(AppError):
    status_code = 502
    code = "asr_provider_failure"

    def __init__(self, message: str, error_class: str = "UNKNOWN") -> None:
        self.error_class = error_class
        super().__init__(message)


class DatabaseError(AppError):
    status_code = 500
    code = "database_failure"
