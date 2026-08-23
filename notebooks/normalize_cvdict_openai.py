#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dictionary_pipeline.database import import_validated  # noqa: E402
from dictionary_pipeline.manual import build_manual_record, save_manual_record, sync_manual_record_with_compose  # noqa: E402
from dictionary_pipeline.openai_batch import (  # noqa: E402
    OpenAIBatchClient,
    Workspace,
    prepare_requests,
    process_output_file,
)
from dictionary_pipeline.source import parse_cvdict  # noqa: E402
from dictionary_pipeline.storage import iter_jsonl, read_json, write_json_atomic, write_jsonl_atomic  # noqa: E402


DEFAULT_SOURCE = PROJECT_ROOT / "backend" / "app" / "data" / "CVDICT.u8"
DEFAULT_WORKSPACE = PROJECT_ROOT / "data" / "openai_dictionary_normalization"
DEFAULT_MODEL = os.getenv("OPENAI_DICTIONARY_MODEL", "gpt-4o-mini")


def workspace_from(args: argparse.Namespace) -> Workspace:
    return Workspace(Path(args.workspace).resolve())


def client_from_env() -> OpenAIBatchClient:
    return OpenAIBatchClient(os.getenv("OPENAI_API_KEY", ""))


def command_prepare(args: argparse.Namespace) -> None:
    workspace = workspace_from(args)
    manifest = read_json(workspace.manifest, {}) or {}
    if manifest.get("openai_batch_status") in {
        "validating", "in_progress", "finalizing", "cancelling",
    }:
        raise RuntimeError("An OpenAI batch is still active; download/cancel it before preparing new requests")
    entries = parse_cvdict(Path(args.source).resolve(), args.limit)
    result = prepare_requests(
        entries,
        workspace,
        args.model,
        args.batch_size,
        args.max_input_chars,
        args.max_requests_per_openai_batch,
        args.include_review,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


async def command_submit(args: argparse.Namespace) -> None:
    batch = await client_from_env().submit(workspace_from(args))
    print(json.dumps(batch, ensure_ascii=False, indent=2))


async def command_status(args: argparse.Namespace) -> None:
    batch = await client_from_env().status(workspace_from(args))
    summary = {
        "id": batch.get("id"),
        "status": batch.get("status"),
        "request_counts": batch.get("request_counts"),
        "output_file_id": batch.get("output_file_id"),
        "error_file_id": batch.get("error_file_id"),
        "usage": batch.get("usage"),
        "errors": batch.get("errors"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


async def command_download(args: argparse.Namespace) -> None:
    workspace = workspace_from(args)
    output_path, error_path = await client_from_env().download(workspace)
    counts = process_output_file(workspace, output_path)
    print(json.dumps({**counts, "raw_output": str(output_path), "raw_errors": str(error_path) if error_path else None}, ensure_ascii=False, indent=2))


def command_validate(args: argparse.Namespace) -> None:
    counts = process_output_file(workspace_from(args), Path(args.output).resolve())
    print(json.dumps(counts, ensure_ascii=False, indent=2))


def command_export(args: argparse.Namespace) -> None:
    workspace = workspace_from(args)
    output_path = Path(args.output).resolve()
    entries = [
        row["entry"]
        for row in iter_jsonl(workspace.completed)
        if row.get("status") in {"validated", "reference"} and row.get("entry")
    ]
    write_jsonl_atomic(output_path, entries)
    print(json.dumps({"exported": len(entries), "output": str(output_path)}, ensure_ascii=False))


async def command_import(args: argparse.Namespace) -> None:
    if not args.confirm_reviewed:
        raise RuntimeError("Refusing to import before review; pass --confirm-reviewed after inspecting the output")
    database_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL or --database-url is required")
    workspace = workspace_from(args)
    result = await import_validated(database_url, workspace.sources, workspace.completed)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def command_manual_upsert(args: argparse.Namespace) -> None:
    workspace = workspace_from(args)
    source, completed = build_manual_record(
        traditional=args.traditional,
        simplified=args.simplified,
        pinyin_number=args.pinyin_number,
        meaning=args.meaning,
        part_of_speech=args.part_of_speech,
        definition=args.definition,
        example_zh=args.example_zh,
        example_pinyin=args.example_pinyin,
        example_vi=args.example_vi,
        hsk_level=args.hsk_level,
    )
    save_manual_record(workspace.sources, workspace.completed, source, completed)
    if args.sync_compose:
        sync_manual_record_with_compose(source, completed, args.compose_file)
    print(
        json.dumps(
            {
                "id": source.id,
                "source_entries": str(workspace.sources),
                "completed": str(workspace.completed),
                "database_synced": args.sync_compose,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def command_resume(args: argparse.Namespace) -> None:
    workspace = workspace_from(args)
    client = client_from_env()
    batch = await client.status(workspace)
    if batch.get("status") == "completed":
        output_path, error_path = await client.download(workspace)
        counts = process_output_file(workspace, output_path)
        manifest = read_json(workspace.manifest, {}) or {}
        pending = sum(item.get("status") == "pending" for item in manifest.get("batch_queue") or [])
        result = {**counts, "raw_output": str(output_path), "raw_errors": str(error_path) if error_path else None, "pending_batches": pending}
        if pending and args.submit_next:
            next_batch = await client.submit(workspace)
            result["next_batch"] = {"id": next_batch.get("id"), "status": next_batch.get("status")}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(json.dumps({"id": batch.get("id"), "status": batch.get("status"), "request_counts": batch.get("request_counts"), "usage": batch.get("usage")}, ensure_ascii=False, indent=2))


def log_queue(message: str, **fields: object) -> None:
    print(
        json.dumps(
            {"time": datetime.now(UTC).isoformat(), "message": message, **fields},
            ensure_ascii=False,
        ),
        flush=True,
    )


async def command_run_queue(args: argparse.Namespace) -> None:
    workspace = workspace_from(args)
    client = client_from_env()
    terminal_failures = {"failed", "expired", "cancelled"}
    while True:
        manifest = read_json(workspace.manifest, {}) or {}
        queue = manifest.get("batch_queue") or []
        if not queue:
            raise RuntimeError("No batch queue. Run prepare first.")
        active = next(
            (item for item in queue if item.get("status") in {"validating", "in_progress", "finalizing"}),
            None,
        )
        if active:
            manifest["openai_batch_id"] = active["batch_id"]
            manifest["openai_batch_status"] = active["status"]
            write_json_atomic(workspace.manifest, manifest)
            batch = await client.status(workspace)
            log_queue(
                "batch_status",
                index=active["index"],
                batch_id=batch.get("id"),
                status=batch.get("status"),
                request_counts=batch.get("request_counts"),
            )
            if batch.get("status") == "completed":
                output_path, error_path = await client.download(workspace)
                counts = process_output_file(workspace, output_path)
                log_queue(
                    "batch_processed",
                    index=active["index"],
                    counts=counts,
                    raw_output=str(output_path),
                    raw_errors=str(error_path) if error_path else None,
                    usage=batch.get("usage"),
                )
                continue
            if batch.get("status") in terminal_failures:
                raise RuntimeError(f"Batch {batch.get('id')} ended with {batch.get('status')}: {batch.get('errors')}")
            await asyncio.sleep(args.poll_seconds)
            continue

        pending = [item for item in queue if item.get("status") == "pending"]
        if pending:
            batch = await client.submit(workspace)
            log_queue(
                "batch_submitted",
                index=pending[0]["index"],
                batch_id=batch.get("id"),
                status=batch.get("status"),
            )
            await asyncio.sleep(args.poll_seconds)
            continue

        failed = [item for item in queue if item.get("status") in terminal_failures]
        if failed:
            raise RuntimeError(f"Queue contains failed batches: {[item['index'] for item in failed]}")
        log_queue("queue_completed", batches=len(queue))
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize CVDICT with OpenAI Batch API")
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Parse CVDICT and create Batch API JSONL")
    prepare.add_argument("--source", default=str(DEFAULT_SOURCE))
    prepare.add_argument("--model", default=DEFAULT_MODEL)
    prepare.add_argument("--limit", type=int)
    prepare.add_argument("--batch-size", type=int, default=75)
    prepare.add_argument("--max-input-chars", type=int, default=60_000)
    prepare.add_argument("--max-requests-per-openai-batch", type=int, default=200)
    prepare.add_argument("--include-review", action="store_true")
    prepare.set_defaults(handler=command_prepare)

    for name, handler, help_text in (
        ("submit", command_submit, "Upload requests and create an OpenAI batch"),
        ("status", command_status, "Check the current OpenAI batch"),
        ("download", command_download, "Download and validate a completed batch"),
        ("resume", command_resume, "Check and download the current batch when ready"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        if name == "resume":
            command.add_argument("--submit-next", action="store_true")
        command.set_defaults(handler=handler)

    validate = subparsers.add_parser("validate", help="Reprocess a saved raw output JSONL")
    validate.add_argument("--output", required=True)
    validate.set_defaults(handler=command_validate)

    export = subparsers.add_parser("export", help="Export clean dictionary entry JSONL")
    export.add_argument("--output", default=str(DEFAULT_WORKSPACE / "normalized_entries.jsonl"))
    export.set_defaults(handler=command_export)

    importer = subparsers.add_parser("import", help="Import validated entries into PostgreSQL")
    importer.add_argument("--database-url")
    importer.add_argument("--confirm-reviewed", action="store_true")
    importer.set_defaults(handler=command_import)

    manual = subparsers.add_parser("manual-upsert", help="Add a reviewed entry and optionally sync Docker PostgreSQL")
    manual.add_argument("--traditional", required=True)
    manual.add_argument("--simplified", required=True)
    manual.add_argument("--pinyin-number", required=True)
    manual.add_argument("--meaning", required=True)
    manual.add_argument("--part-of-speech", default="phrase")
    manual.add_argument("--definition", default="")
    manual.add_argument("--example-zh")
    manual.add_argument("--example-pinyin")
    manual.add_argument("--example-vi")
    manual.add_argument("--hsk-level", type=int)
    manual.add_argument("--sync-compose", action="store_true")
    manual.add_argument("--compose-file")
    manual.set_defaults(handler=command_manual_upsert)

    runner = subparsers.add_parser("run-queue", help="Process queued OpenAI batches sequentially")
    runner.add_argument("--poll-seconds", type=int, default=60)
    runner.set_defaults(handler=command_run_queue)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.handler(args)
    if asyncio.iscoroutine(result):
        asyncio.run(result)


if __name__ == "__main__":
    main()
