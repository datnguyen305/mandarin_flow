import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CookieSessionStore:
    """Stores non-sensitive cookie session metadata beside the runtime cookie file."""

    def __init__(self, cookies_path: Path | None) -> None:
        self.metadata_path = cookies_path.with_name(f"{cookies_path.name}.status.json") if cookies_path else None

    def mark_probe_success(self) -> None:
        self._update(status="valid", last_verified_at=self._now(), last_error=None)

    def mark_download_success(self) -> None:
        self._update(status="valid", last_success_at=self._now(), last_error=None)

    def mark_needs_refresh(self, error_class: str) -> None:
        self._update(status="needs_refresh", last_error=error_class)

    def mark_media_error(self, error_class: str) -> None:
        self._update(last_error=error_class)

    def _update(self, **changes: Any) -> None:
        if not self.metadata_path:
            return
        metadata: dict[str, Any] = {}
        try:
            if self.metadata_path.exists():
                metadata = json.loads(self.metadata_path.read_text())
        except (OSError, json.JSONDecodeError):
            metadata = {}
        metadata.setdefault("status", "unknown")
        metadata.update(changes)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(prefix="cookie-status-", dir=self.metadata_path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(metadata, handle, separators=(",", ":"))
                handle.write("\n")
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.metadata_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
