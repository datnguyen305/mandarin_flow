"""Review dictionary crawl errors with OpenAI without touching the live crawl CSV."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "hanngubackinh_crawl" / "hanngubackinh_enrichment.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "hanngubackinh_crawl" / "openai_error_review.csv"
FIELDS = ["word", "pinyin", "han_viet", "meaning", "definition", "part_of_speech", "examples_json", "source", "status", "error"]
MODEL = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")


def read_errors() -> list[dict[str, str]]:
    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("status") == "error" and row.get("word")]


def read_checkpoint() -> dict[str, dict[str, str]]:
    if not OUTPUT_PATH.exists():
        return {}
    with OUTPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        return {row["word"]: row for row in csv.DictReader(file) if row.get("word")}


def write_checkpoint(rows: dict[str, dict[str, str]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows.values())


def extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    return json.loads(candidate)


def extract_output_text(payload: dict) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                parts.append(content.get("text", ""))
    if parts:
        return "".join(parts)
    return payload.get("output_text", "")


def prompt_for(row: dict[str, str]) -> str:
    return f"""You review a Chinese-Vietnamese dictionary crawl error.
Return only valid JSON. Do not invent facts, place locations, names, or rare meanings.
Use natural modern Mandarin and Vietnamese. If the word is not a Chinese lexical item
or cannot be identified confidently, set status to uncertain and leave meaning empty.
Provide a short learner-friendly definition and at most two short examples.
Use pinyin with tone marks. The examples must contain Chinese, pinyin, and Vietnamese.

JSON schema:
{{"word": string, "pinyin": string, "han_viet": string, "meaning": string,
"definition": string, "part_of_speech": string, "examples": [{{"chinese": string,
"pinyin": string, "vietnamese": string}}], "status": "reviewed"|"uncertain"}}

Input word: {json.dumps(row['word'], ensure_ascii=False)}
Crawler error: {json.dumps(row.get('error', ''), ensure_ascii=False)}"""


async def review_word(client: httpx.AsyncClient, row: dict[str, str], api_key: str, model: str) -> dict[str, str]:
    payload = {
        "model": model,
        "input": prompt_for(row),
        "temperature": 0.1,
    }
    last_error = ""
    for attempt in range(2):
        try:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = extract_json(extract_output_text(response.json()))
            status = data.get("status") if data.get("status") in {"reviewed", "uncertain"} else "uncertain"
            examples = data.get("examples") if isinstance(data.get("examples"), list) else []
            return {
                "word": row["word"],
                "pinyin": str(data.get("pinyin") or ""),
                "han_viet": str(data.get("han_viet") or ""),
                "meaning": str(data.get("meaning") or ""),
                "definition": str(data.get("definition") or ""),
                "part_of_speech": str(data.get("part_of_speech") or ""),
                "examples_json": json.dumps(examples[:2], ensure_ascii=False),
                "source": "openai_review",
                "status": status,
                "error": "",
            }
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            await asyncio.sleep(2**attempt)
    return {"word": row["word"], "source": "openai_review", "status": "error", "error": last_error}


async def review(rows: list[dict[str, str]], delay: float, model: str) -> dict[str, dict[str, str]]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY chưa được thiết lập")
    checkpoint = read_checkpoint()
    pending = [row for row in rows if row["word"] not in checkpoint]
    async with httpx.AsyncClient(timeout=45) as client:
        for index, row in enumerate(pending, start=1):
            checkpoint[row["word"]] = await review_word(client, row, api_key, model)
            write_checkpoint(checkpoint)
            print(f"Reviewed {index}/{len(pending)}: {row['word']}", flush=True)
            await asyncio.sleep(delay)
    return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    rows = read_errors()[: args.limit]
    result = asyncio.run(review(rows, args.delay, args.model))
    print(f"Saved {len(result)} reviews to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
