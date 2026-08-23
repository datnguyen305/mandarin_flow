import { beforeEach, describe, expect, it } from "vitest";
import type { ProcessingProgress } from "@/types";
import {
  IMPORT_PROCESSING_TASK_KEY,
  createImportProcessingJob,
  mergeServerProgress,
  readImportProcessingJob,
  removeImportProcessingJob,
  writeImportProcessingJob,
} from "./importProcessing";

function progress(value: number, overrides: Partial<ProcessingProgress> = {}): ProcessingProgress {
  return {
    video_id: "video-1",
    status: "processing",
    processed_batches: 0,
    total_batches: 2,
    processed_subtitles: 0,
    total_subtitles: 60,
    progress: value,
    ...overrides,
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("persisted import job", () => {
  it("stores only reconnect metadata, not authoritative progress", () => {
    const job = createImportProcessingJob("video-1", "https://youtube.com/watch?v=video-1");
    writeImportProcessingJob(job);

    const raw = window.localStorage.getItem(IMPORT_PROCESSING_TASK_KEY);
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw ?? "{}")).toEqual(expect.objectContaining({
      videoId: "video-1",
      url: "https://youtube.com/watch?v=video-1",
    }));
    expect(JSON.parse(raw ?? "{}")).not.toHaveProperty("progress");
    expect(readImportProcessingJob()?.videoId).toBe("video-1");
  });

  it("drops old task payloads that contain local progress", () => {
    window.localStorage.setItem(IMPORT_PROCESSING_TASK_KEY, JSON.stringify({
      videoId: "video-1",
      url: "https://youtube.com/watch?v=video-1",
      progress: progress(0.5),
    }));

    expect(readImportProcessingJob()).toBeNull();
    expect(window.localStorage.getItem(IMPORT_PROCESSING_TASK_KEY)).toBeNull();
  });

  it("can clear without broadcasting when UI state is already controlled", () => {
    const job = createImportProcessingJob("video-1", "https://youtube.com/watch?v=video-1");
    writeImportProcessingJob(job);
    removeImportProcessingJob(false);
    expect(readImportProcessingJob()).toBeNull();
  });
});

describe("mergeServerProgress", () => {
  it("does not let out-of-order responses move progress backwards", () => {
    expect(mergeServerProgress(progress(0.72), progress(0.68)).progress).toBe(0.72);
  });

  it("resets progress when a different job is received", () => {
    expect(mergeServerProgress(progress(0.72), progress(0.1, { video_id: "video-2" })).progress).toBe(0.1);
  });

  it("applies completed immediately at 100 percent", () => {
    const merged = mergeServerProgress(progress(0.72), progress(0.8, { status: "completed" }));
    expect(merged.status).toBe("completed");
    expect(merged.progress).toBe(1);
    expect(merged.phase).toBe("completed");
  });
});
