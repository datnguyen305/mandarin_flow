"""Export Firefox cookies after a Telegram-approved cookie request.

This helper must run on the host that owns the Firefox profile. It accepts no
shell command from Telegram; the yt-dlp arguments below are fixed.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


API_BASE_URL = os.getenv("MANDARINFLOW_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEV_TOKEN = os.environ["DEV_ACCESS_TOKEN"]
OUTPUT = Path(os.getenv("MANDARINFLOW_COOKIES_FILE", "cookies/cookies.txt")).resolve()
POLL_SECONDS = int(os.getenv("MANDARINFLOW_COOKIE_POLL_SECONDS", "5"))
FIREFOX_PROFILE = os.getenv("MANDARINFLOW_FIREFOX_PROFILE", "")


def api_request(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        f"{API_BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-Dev-Token": DEV_TOKEN},
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def export_cookies(source_url: str | None = None) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="cookies-", suffix=".txt", dir=OUTPUT.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        # yt-dlp expects the destination not to exist yet. An empty pre-created
        # file is interpreted as an invalid Netscape cookie file.
        temporary_path.unlink(missing_ok=True)
        url = source_url or "https://www.youtube.com/"
        browser = "firefox" if not FIREFOX_PROFILE else f"firefox:{FIREFOX_PROFILE}"
        result = subprocess.run(
            [
                os.environ.get("PYTHON", "python"),
                "-m",
                "yt_dlp",
                "--cookies-from-browser",
                browser,
                "--cookies",
                str(temporary_path),
                "--skip-download",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        exported = temporary_path.exists() and temporary_path.stat().st_size > 32
        if result.returncode != 0 and not exported:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            message = detail[-1] if detail else "unknown yt-dlp error"
            raise RuntimeError(f"yt-dlp could not export Firefox cookies: {message[:500]}")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            print(f"yt-dlp validation warning; cookies were exported: {detail[-1] if detail else 'unknown error'}")
        if not temporary_path.stat().st_size:
            raise RuntimeError("yt-dlp exported an empty cookies file")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, OUTPUT)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    print(f"Watching for approved cookie requests; output={OUTPUT}")
    while True:
        try:
            requests = api_request("GET", "/api/agent/requests")
            for item in requests:
                if item.get("type") != "cookie_update" or item.get("status") != "approved":
                    continue
                request_id = item["id"]
                try:
                    export_cookies(item.get("payload", {}).get("youtube_url"))
                    api_request("POST", f"/api/agent/requests/{request_id}/cookie-export-result", {"success": True})
                    print(f"Exported cookies for {request_id}")
                except Exception as exc:
                    api_request(
                        "POST",
                        f"/api/agent/requests/{request_id}/cookie-export-result",
                        {"success": False, "error": str(exc)[:500]},
                    )
                    print(f"Cookie export failed for {request_id}: {exc}")
        except Exception as exc:
            print(f"Helper connection failed: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
