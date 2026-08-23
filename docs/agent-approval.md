# Agent Approval Flow

MandarinFlow agents can suggest video or dictionary imports, but they never execute an import directly.

```text
agent request -> agent_requests (pending) -> Telegram -> approve/reject -> execution
```

## Environment

Set these backend variables without committing their values:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
TELEGRAM_ALLOWED_USER_ID=
TELEGRAM_WEBHOOK_SECRET=
AGENT_REQUEST_EXPIRY_HOURS=24
```

`TELEGRAM_ALLOWED_USER_ID` is the numeric Telegram user ID allowed to approve requests. The webhook also requires the configured secret header from Telegram.

After deployment, configure the webhook with the public HTTPS URL:

```text
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<domain>/api/agent/integrations/telegram/webhook&secret_token=<WEBHOOK_SECRET>
```

## Agent endpoints

The request endpoints require `X-Dev-Token` and only create `pending` records:

```text
POST /api/agent/requests/video
POST /api/agent/requests/vocabulary
POST /api/agent/requests/cookies
GET  /api/agent/requests
GET  /api/agent/requests/{id}

## Telegram video import

The configured Telegram user can create a video import request from the bot:

```text
/import https://www.youtube.com/watch?v=<video-id>
```

Sending a YouTube URL by itself is also supported. The bot creates the same
pending `video_import` request as the API and sends an approval message with
`Approve` and `Reject` buttons. It does not start processing directly from an
incoming message. This keeps the existing approval guard and restricts both
messages and callbacks to `TELEGRAM_ALLOWED_USER_ID` and
`TELEGRAM_ADMIN_CHAT_ID`.

The webhook must point to the backend endpoint shown below; Telegram delivers
both text messages and approval callbacks to the same endpoint.
```

Approval from the API is also protected by `X-Dev-Token`. Telegram approval additionally verifies the webhook secret and the Telegram user ID. Repeated approval callbacks are rejected by the database state transition guard.

The `agent_requests` migration is `0008_agent_requests`. A failed Telegram notification does not roll back the database request; the request remains pending and its error is recorded for retry/inspection.

## Cookie safety

`request_cookie_update` never reads or transfers browser cookies. The local helper at `scripts/cookie_export_helper.py` runs on the machine that owns Firefox, watches for a Telegram-approved cookie request, executes only the fixed `yt-dlp --cookies-from-browser firefox --cookies ...` command, and writes the result to `cookies/cookies.txt`. Cookie contents are never sent to the agent, Telegram, OpenAI, or PostgreSQL.

Start the helper locally:

```bash
DEV_ACCESS_TOKEN=dev-local python scripts/cookie_export_helper.py
```

Keep Firefox closed while the export runs. The helper reports only success/failure to the backend.

To run it continuously on a Linux development machine, install the example
systemd user service at `scripts/mandarinflow-cookie-helper.service.example`.
Replace `/ABSOLUTE/PATH/youtube-language-learning` in the service with the real
project path, then create the token file:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/mandarinflow-cookie-helper.service.example \
  ~/.config/systemd/user/mandarinflow-cookie-helper.service

cat > .env.cookie-helper <<'EOF'
DEV_ACCESS_TOKEN=dev-local
MANDARINFLOW_API_URL=http://127.0.0.1:8000
EOF
chmod 600 .env.cookie-helper

systemctl --user daemon-reload
systemctl --user enable --now mandarinflow-cookie-helper.service
systemctl --user status mandarinflow-cookie-helper.service
```

After this, pressing **Approve** in Telegram automatically makes the helper
export Firefox cookies and update the request. It never executes arbitrary
commands received from Telegram.
