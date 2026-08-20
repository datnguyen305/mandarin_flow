# Project Handoff

This file captures the current state of the project for future Codex sessions.

## Project

Root path:

```text
/home/datnguyen/Documents/GIT_PROJECT/learning_chinese_through_vid/youtube-language-learning
```

The app is a Dockerized Chinese-learning tool:

- Frontend: Next.js app in `frontend/`
- Backend: FastAPI app in `backend/`
- Database: PostgreSQL
- Cache/queue support: Redis

Primary user flow:

1. Home page `/` imports a YouTube video URL.
2. Video list page `/videos` shows imported videos.
3. Clicking a video opens `/watch?v=<youtube_id>`.
4. Watch page shows YouTube player, interactive subtitles, word list, transcript, dictionary lookup, and save-to-vocabulary.
5. Vocabulary page `/vocabulary` shows saved words.

## Anonymous Guest Data

- Users do not log in. `get_or_create_guest()` creates a random token and sends it as the HttpOnly `mandarinflow_guest` cookie.
- PostgreSQL stores only the SHA-256 token hash in `guest_sessions`; raw tokens never enter the database.
- `saved_vocabulary.guest_id` isolates vocabulary by browser guest.
- `guest_video_progress` stores a separate playback position for each guest/video pair.
- The home page resumes a video from the current guest's saved position.
- Video, subtitles, dictionary data, and dictionary cache remain shared globally.
- Dictionary enrichment uses Redis as a fast TTL cache and PostgreSQL table `dictionary_enrichment_cache` as the persistent cache. Lookup order is Redis -> PostgreSQL -> OpenAI/fallback provider.
- Dev access still uses `X-Dev-Token`; it is separate from guest identity.
- Migration `0003_guest_sessions` preserves old `user_id=1` vocabulary under an inaccessible legacy guest instead of deleting it.
- Production Compose sets `ENVIRONMENT=production`, making the guest cookie `Secure`; frontend requests use `credentials: "include"`.
- Clearing cookies, private browsing, or switching browsers creates a different guest. There is no cross-device recovery in this MVP.

## Current Docker State

The app is expected to run with:

```bash
docker compose up --build -d
```

Production deployment is image-based: `.github/workflows/deploy.yml` builds backend/frontend, pushes SHA and `latest` tags to GHCR, then pulls the exact SHA on the VPS. `docker-compose.prod.yml` does not build application images on the VPS.

URLs:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
Docs:     http://localhost:8000/docs
```

Expected services:

- `frontend` on port `3000`
- `backend` on port `8000`
- `postgres`
- `redis`

## Current Frontend Layout

Navigation:

- `Import` -> `/`
- `Video` -> `/videos`
- `Từ vựng` -> `/vocabulary`

Important frontend files:

- `frontend/src/components/AppHeader.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/videos/page.tsx`
- `frontend/src/app/watch/page.tsx`
- `frontend/src/components/DictionaryPanel.tsx`
- `frontend/src/components/HanziStrokeWriter.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/types.ts`

Current UI decisions:

- Home `/` is the import page.
- Home `/` also has a YouTube cookies form:
  - User can paste cookies or load a `.txt` file in the browser.
  - Frontend posts JSON to `POST /api/videos/cookies`.
  - Backend writes the content to `settings.yt_dlp_cookies_file`, normally `/app/cookies/cookies.txt`.
  - Docker Compose mounts `./cookies:/app/cookies` writable so the backend can save the file.
- `/videos` is the imported video list.
- Video cards open `/watch?v=<youtube_video_id>`.
- The `Video` nav tab remembers the last watched video when navigating back from `/vocabulary`.
  - `frontend/src/app/watch/page.tsx` saves `fluentmandarin:last-watch-href` to `localStorage`.
  - `frontend/src/components/AppHeader.tsx` reads that value when the user is on `/vocabulary`.
  - The saved href includes approximate playback time as `t=<seconds>`.
- `/watch` uses a two-column desktop layout:
  - Left column: video player, then `Phụ đề tương tác` below it.
  - Right column: sidebar with `Phụ đề` tab on the left and `Từ trong câu` tab on the right.
- `Phụ đề tương tác` no longer shows the old `Lân cận` nearby-subtitles block.
- In `Phụ đề tương tác`, pinyin is displayed above each segmented word token.
- `Từ điển nhanh` includes Hanzi Writer stroke-order animation for the selected Chinese character/token.
  - Dependency: `hanzi-writer` in `frontend/package.json`.
  - For multi-character words, the writer shows one character at a time with character selector buttons.
  - The compact writer is displayed beside the selected word/pinyin in the dictionary header card.
  - Hanzi Writer loads stroke data from its default CDN behavior.
- The small video ID/progress line under the video title was removed; only the video title is shown.
- Sidebar font sizes were increased for tabs, word cards, transcript rows, and footer count.
- Transcript sidebar auto-scrolls the active subtitle into view when the `Phụ đề` tab is selected.
- Watch page has a `Video` back button that links to `/videos`.
- When route is `/watch`, the `Video` nav item is active.
- A floating mini player is mounted globally through `frontend/src/components/FloatingVideoPlayer.tsx`.
  - It appears outside `/watch` when a last watched video exists.
  - It uses the saved `/watch?v=...&t=...` href and embeds the YouTube video near the last known timestamp.
  - This is an in-app floating player, not true browser Picture-in-Picture.

## OpenAI Translation

The backend now supports full-sentence subtitle translation with OpenAI instead of word-by-word gloss fallback.

Relevant files:

- `backend/app/services/translation_service.py`
- `backend/app/api/deps.py`
- `backend/app/core/config.py`
- `docker-compose.yml`
- `.env`
- `.env.example`
- `README.md`
- `backend/tests/test_openai_translation_provider.py`

Current `.env` should contain:

```env
TRANSLATION_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_TRANSLATION_MODEL=gpt-4o-mini
```

Do not print or expose the actual API key in responses.

Implementation details:

- `OpenAITranslationProvider` calls `POST https://api.openai.com/v1/responses` using `httpx`.
- It asks the model to return a JSON array of Vietnamese translations in the same order as the input subtitles.
- Parser accepts clean JSON arrays and common model output wrappers:
  - raw `["..."]`
  - fenced ```json blocks
  - extra leading text before the JSON array
- Translation cache key is based on source/target and the input text batch.

Important behavior:

- Already processed videos may still have old translations in PostgreSQL/Redis.
- To force OpenAI translation for an old video, delete that video in the UI and import it again, or manually clear/reprocess its batches.

## Subtitle Processing Notes

Relevant backend files:

- `backend/app/services/subtitle_service.py`
- `backend/app/services/subtitle_queue.py`
- `backend/app/repositories/video_repository.py`
- `backend/app/repositories/subtitle_repository.py`
- `backend/app/repositories/batch_repository.py`
- `backend/app/api/videos.py`
- `backend/app/schemas/video.py`

Current behavior:

- Backend first tries YouTube subtitles.
- If subtitles are unavailable and `ASR_PROVIDER=openai`, it falls back to OpenAI ASR.
- Current local `.env` sets `ASR_MAX_DURATION_SECONDS=1800` so videos around 1030 seconds can pass the MVP ASR duration guard.
- Subtitle batches are processed progressively.
- The frontend listens over SSE at:

```text
GET /api/videos/{video_id}/subtitles/stream
```

Fixed bugs:

- SQLAlchemy async `greenlet_spawn has not been called` after batch rollback:
  - Cause: ORM objects were read after `rollback()`.
  - Fix: `process_batch` stores scalar values before `try` and uses `set_processing_status_by_id`.
- Duplicate video insert race:
  - Cause: two process requests could insert the same `youtube_video_id`.
  - Fix: `VideoRepository.upsert()` catches `IntegrityError`, rolls back, fetches existing video, and updates it.
- SSE stream before video exists:
  - Cause: stream raised `SubtitlesUnavailableError` and produced ASGI errors.
  - Fix: stream now emits `processing_failed` and returns.
- OpenAI translation JSON parse error:
  - Cause: model sometimes returned markdown or extra text.
  - Fix: parser extracts JSON array from common wrappers.

## Verification Commands

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm test
npm run build
```

Docker restart:

```bash
docker compose up --build -d backend frontend
```

Check services:

```bash
docker compose ps
curl -I http://localhost:3000
curl -I http://localhost:8000/docs
docker compose logs --tail=120 backend
```

Recent passing checks:

- Backend `pytest`: 44 passed
- Frontend `npm run lint`: passed
- Frontend `npm test`: 10 passed
- Frontend `npm run build`: passed
- Frontend container was rebuilt/restarted after the latest sidebar tab order and watch title cleanup changes.

## Known Caveats

- This workspace did not appear to be a git repository when checked from the root and project directory.
- Docker Compose rebuilds can take a while because frontend image export is slow after Next build.
- If a video has no YouTube transcript, processing depends on OpenAI ASR, valid YouTube cookies/audio availability, and the configured `ASR_MAX_DURATION_SECONDS`.
- If the UI shows stale `[vi] ...` translations, the video was likely processed before OpenAI translation was enabled.
- The current frontend still has a fallback to display token meanings if a translation starts with `[vi]`, but with OpenAI translation enabled this should be uncommon for newly processed videos.
- The `Video` nav tab intentionally reopens the last watched video from `/vocabulary`; use the in-watch `Video` back button or `/videos` directly to reach the list.
- The floating mini player cannot preserve the exact same iframe instance across route changes; it reopens the YouTube embed near the saved timestamp.

## Suggested Next Improvements

- Add a visible retry button for failed subtitle batches in the watch page.
- Add a clearer processing status/progress bar on the watch page.
- Add a backend endpoint or UI action to reprocess all failed batches for a video.
- Add a UI action to force retranslate existing processed subtitles with OpenAI.
- Avoid sending duplicate `processVideo` calls if the watch page is opened rapidly or refreshed during processing.
- Persist sidebar tab choice (`Phụ đề` vs `Từ trong câu`) in `localStorage`.
- Consider a separate `Danh sách video` nav or button if users want `Video` to always mean list instead of last watched video.
