import type { ProcessingProgress } from "@/types";

export const IMPORT_PROCESSING_EVENT = "import-processing-updated";
export const IMPORT_PROCESSING_TASK_KEY = "fluentmandarin:import-processing-task";
const JOB_VERSION = 3;

export interface PersistedImportJob {
  version: number;
  videoId: string;
  url: string;
  startedAt: number;
}

export type ProcessingUiState = "idle" | "starting" | "processing" | "completed" | "failed" | "cancelled";

export function createImportProcessingJob(videoId: string, url: string): PersistedImportJob {
  return {
    version: JOB_VERSION,
    videoId,
    url,
    startedAt: Date.now(),
  };
}

export function readImportProcessingJob(): PersistedImportJob | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(IMPORT_PROCESSING_TASK_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<PersistedImportJob> & { progress?: unknown };
    if (value.progress || !value.videoId || !value.url) {
      throw new Error("Invalid import processing job");
    }
    return {
      version: JOB_VERSION,
      videoId: value.videoId,
      url: value.url,
      startedAt: value.startedAt ?? Date.now(),
    };
  } catch {
    window.localStorage.removeItem(IMPORT_PROCESSING_TASK_KEY);
    return null;
  }
}

export function writeImportProcessingJob(job: PersistedImportJob) {
  if (typeof window === "undefined") return;
  const normalized = { ...job, version: JOB_VERSION };
  window.localStorage.setItem(IMPORT_PROCESSING_TASK_KEY, JSON.stringify(normalized));
  window.dispatchEvent(new CustomEvent(IMPORT_PROCESSING_EVENT, { detail: normalized }));
}

export function removeImportProcessingJob(notify = true) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(IMPORT_PROCESSING_TASK_KEY);
  if (notify) window.dispatchEvent(new CustomEvent(IMPORT_PROCESSING_EVENT));
}

export function friendlyProgressMessage(progress: ProcessingProgress | null, state: ProcessingUiState): string {
  if (state === "idle") return "Sẵn sàng xử lý video.";
  if (state === "starting") return "Đang bắt đầu xử lý...";
  if (state === "cancelled") return "Đã dừng theo dõi trạng thái.";
  if (!progress) return "Đang kết nối với máy chủ...";
  if (progress.status === "completed") return "Hoàn tất.";
  if (progress.status === "failed") return "Xử lý bị lỗi.";

  switch (progress.phase) {
    case "metadata":
    case "subtitle_source":
      return "Đang chuẩn bị video.";
    case "youtube_subtitles":
    case "asr":
      return "Đang xử lý phụ đề.";
    case "preparing_batches":
    case "processing_batches":
    case "translating":
    case "segmenting":
      return "Đang phân tích ngôn ngữ.";
    case "saving":
      return "Đang hoàn tất.";
    default:
      return "Đang xử lý video.";
  }
}

export function mergeServerProgress(current: ProcessingProgress | null, incoming: ProcessingProgress): ProcessingProgress {
  if (!current || current.video_id !== incoming.video_id) return incoming;
  if (incoming.status === "completed") return { ...incoming, progress: 1, phase: "completed" };
  if (incoming.status === "failed") return incoming;
  if (current.status === "completed" || current.status === "failed") return current;

  return {
    ...incoming,
    processed_batches: Math.max(current.processed_batches, incoming.processed_batches),
    processed_subtitles: Math.max(current.processed_subtitles, incoming.processed_subtitles),
    total_batches: Math.max(current.total_batches, incoming.total_batches),
    total_subtitles: Math.max(current.total_subtitles, incoming.total_subtitles),
    progress: Math.max(current.progress, incoming.progress),
  };
}

export function stepIndexForProgress(progress: ProcessingProgress | null, state: ProcessingUiState) {
  if (state === "idle" || state === "cancelled") return 0;
  if (!progress) return 0;
  if (progress.status === "completed") return 4;
  if (["subtitle_source", "youtube_subtitles", "asr", "preparing_batches"].includes(progress.phase ?? "")) return 1;
  if (progress.phase === "translating") return 2;
  if (progress.phase === "segmenting") return 3;
  if (progress.phase === "saving") return 4;
  if (progress.progress >= 0.8) return 4;
  if (progress.progress >= 0.55) return 3;
  if (progress.progress >= 0.2) return 2;
  return 0;
}
