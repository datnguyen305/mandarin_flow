"""Crawl the public dictionary endpoint of hanngubackinh.vn into CSV.

The endpoint rejects bare urllib requests with 403, so the crawler uses a
browser context with the site's normal Referer and User-Agent headers.
This source is kept separate from the Hanzii enrichment CSV.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CVDICT_PATH = PROJECT_ROOT / "backend" / "app" / "data" / "CVDICT.u8"
OUTPUT_PATH = PROJECT_ROOT / "data" / "hanngubackinh_crawl" / "hanngubackinh_enrichment.csv"
BASE_URL = "https://hanngubackinh.vn/"
SEARCH_URL = "https://hanngubackinh.vn/api/dict/search?q={}"
DETAIL_URL = "https://hanngubackinh.vn/api/dict/word?hanzi={}"
USER_AGENT = "MandarinFlowDictionaryImporter/1.0 (+https://mandarinflow.online)"
FIELDS = [
    "word", "hanzi", "pinyin", "han_viet", "meaning", "definition", "part_of_speech", "source",
    "hsk_level", "examples_json", "raw_json", "status", "error",
]
CVDICT_PATTERN = re.compile(r"^(?P<traditional>\S+)\s+(?P<simplified>\S+)\s+\[[^\]]+\]")
POS_LABELS_VI = {
    "名": "danh từ",
    "动": "động từ",
    "形": "tính từ",
    "副": "trạng từ",
    "代": "đại từ",
    "介": "giới từ",
    "连": "liên từ",
    "助": "trợ từ",
    "量": "lượng từ",
    "数": "số từ",
    "叹": "thán từ",
    "拟声": "từ tượng thanh",
}


def generate_pinyin(sentence: str) -> str:
    """Generate fallback pinyin only when the source has no pinyin."""
    try:
        from pypinyin import Style, lazy_pinyin

        pinyin = " ".join(lazy_pinyin(sentence, style=Style.TONE))
        return re.sub(r"\s+([，。！？；：、,.!?;:])", r"\1", pinyin)
    except ImportError:
        return ""


def read_words(limit: int | None) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    with CVDICT_PATH.open(encoding="utf-8") as file:
        for line in file:
            match = CVDICT_PATTERN.match(line.strip())
            if not match:
                continue
            word = match.group("simplified")
            if word not in seen:
                words.append(word)
                seen.add(word)
            if limit and len(words) >= limit:
                break
    return words


def read_existing() -> dict[str, dict[str, str]]:
    if not OUTPUT_PATH.exists():
        return {}
    with OUTPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        return {row["word"]: row for row in csv.DictReader(file) if row.get("word")}


def write_rows(rows: dict[str, dict[str, str]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows.values())


async def crawl(
    words: list[str], delay: float, reset: bool = False, workers: int = 8,
    progress_every: int = 1000,
) -> dict[str, dict[str, str]]:
    rows = {} if reset else read_existing()
    pending = [
        word for word in words
        if rows.get(word, {}).get("status") not in {"success", "no_result", "skipped_external"}
    ]
    total = len(words)
    async with async_playwright() as playwright:
        api = await playwright.request.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={"Referer": BASE_URL, "Accept": "application/json"},
        )
        homepage = await api.get(BASE_URL, timeout=30000)
        if homepage.status != 200:
            raise RuntimeError(f"Không mở được trang nguồn: HTTP {homepage.status}")

        async def fetch_json(url: str) -> tuple[int, str]:
            for attempt in range(4):
                response = await api.get(url, timeout=30000, headers={"Accept": "application/json"})
                body = await response.text()
                if response.status != 429 or attempt == 3:
                    return response.status, body
                await asyncio.sleep(2 ** attempt)
            raise RuntimeError("unreachable")

        # Abort before scheduling the full crawl when the site's dictionary
        # function is missing. Otherwise every pending word becomes HTTP 404.
        probe_status, probe_body = await fetch_json(SEARCH_URL.format(quote("学习")))
        if probe_status != 200:
            content_type = "HTML" if probe_body.lstrip().lower().startswith("<!doctype html") else "response"
            raise RuntimeError(
                "API từ điển Hán Ngữ Bắc Kinh không khả dụng: "
                f"HTTP {probe_status} ({content_type}) tại /api/dict/search. "
                "Dừng crawl để không ghi hàng loạt bản ghi lỗi."
            )

        async def crawl_one(index: int, word: str) -> tuple[str, dict[str, str]]:
            try:
                search_status, search_body = await fetch_json(SEARCH_URL.format(quote(word)))
                if search_status != 200:
                    raise RuntimeError(f"HTTP {search_status}")
                data = json.loads(search_body)
                source = data.get("source", "")
                result = (data.get("results") or [{}])[0]
                if not result.get("hanzi"):
                    row = {"word": word, "source": source, "status": "no_result", "error": "Không có kết quả trong database nguồn"}
                    return word, row
                if source != "db":
                    row = {"word": word, "source": source, "status": "skipped_external", "error": "Bỏ qua nguồn ngoài Hán Ngữ Bắc Kinh"}
                    return word, row
                detail_status, detail_body = await fetch_json(DETAIL_URL.format(quote(result["hanzi"])))
                if detail_status != 200:
                    raise RuntimeError(f"Detail HTTP {detail_status}")
                detail = json.loads(detail_body)
                examples = [
                    {
                        "chinese": item.get("simplified", ""),
                        "pinyin": item.get("pinyin") or generate_pinyin(item.get("simplified", "")),
                        "vietnamese": item.get("vietnamese", ""),
                        "source": item.get("source", ""),
                    }
                    for group in (detail.get("examples") or {}).values()
                    for item in group
                    if item.get("simplified") and item.get("vietnamese")
                ]
                part_of_speech = "; ".join(
                    POS_LABELS_VI.get(label, label)
                    for label in (detail.get("posLabels") or [])
                )
                rows[word] = {
                    "word": word,
                    "hanzi": result.get("hanzi", ""),
                    "pinyin": result.get("pinyin", ""),
                    "han_viet": result.get("hanViet", ""),
                    "meaning": result.get("glossVi", ""),
                    "definition": detail.get("definitionVi", ""),
                    "part_of_speech": part_of_speech,
                    "source": source,
                    "hsk_level": str(detail.get("hskLevel") or ""),
                    "examples_json": json.dumps(examples, ensure_ascii=False),
                    "raw_json": json.dumps({"search": result, "detail": detail}, ensure_ascii=False),
                    "status": "success",
                    "error": "",
                }
                row = rows[word]
                return word, row
            except Exception as exc:  # keep the batch resumable
                row = {"word": word, "status": "error", "error": str(exc)}
                return word, row

        for start in range(0, len(pending), max(1, workers)):
            batch = pending[start : start + max(1, workers)]
            results = await asyncio.gather(
                *(crawl_one(start + offset + 1, word) for offset, word in enumerate(batch))
            )
            for word, row in results:
                rows[word] = row
            write_rows(rows)
            processed = start + len(batch)
            if processed % progress_every < max(1, workers) or processed == len(pending):
                counts = {status: sum(row.get("status") == status for row in rows.values()) for status in ("success", "no_result", "skipped_external", "error")}
                print(f"Progress {processed}/{len(pending)} pending; total={total}; {counts}", flush=True)
            if delay:
                await asyncio.sleep(delay)
        await api.dispose()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--words", nargs="+", help="Danh sách từ muốn test, cách nhau bằng khoảng trắng")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=1000)
    parser.add_argument("--reset", action="store_true", help="Xóa checkpoint CSV trước khi chạy")
    args = parser.parse_args()
    words = args.words or read_words(args.limit)
    rows = asyncio.run(crawl(words, args.delay, args.reset, args.workers, args.progress_every))
    print(f"Saved {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
