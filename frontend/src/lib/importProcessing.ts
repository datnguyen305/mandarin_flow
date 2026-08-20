import type { ProcessingProgress } from "@/types";

export const IMPORT_PROCESSING_EVENT = "import-processing-updated";
export const IMPORT_PROCESSING_TASK_KEY = "fluentmandarin:import-processing-task";

export interface ImportProcessingTask {
  videoId: string;
  url: string;
  progress: ProcessingProgress;
  message: string;
  error?: string | null;
  updatedAt: number;
}

export function readImportProcessingTask(): ImportProcessingTask | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(IMPORT_PROCESSING_TASK_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ImportProcessingTask;
  } catch {
    window.localStorage.removeItem(IMPORT_PROCESSING_TASK_KEY);
    return null;
  }
}

export function writeImportProcessingTask(task: ImportProcessingTask) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(IMPORT_PROCESSING_TASK_KEY, JSON.stringify(task));
  window.dispatchEvent(new CustomEvent(IMPORT_PROCESSING_EVENT, { detail: task }));
}

export function removeImportProcessingTask() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(IMPORT_PROCESSING_TASK_KEY);
  window.dispatchEvent(new CustomEvent(IMPORT_PROCESSING_EVENT));
}

export function progressMessage(progress: ProcessingProgress) {
  if (progress.status === "completed") return "Đã xử lý xong.";
  if (progress.status === "failed") return "Xử lý bị dừng.";
  if (!progress.total_batches) return "Đang chuẩn bị phụ đề...";
  return `Đang xử lý phụ đề: ${Math.round(progress.progress * 100)}%`;
}

export function stepIndexForProgress(progress: ProcessingProgress | null, loading: boolean) {
  if (!loading && !progress) return 0;
  if (!progress) return 1;
  if (progress.status === "completed") return 4;
  if (progress.progress >= 0.8) return 4;
  if (progress.progress >= 0.55) return 3;
  if (progress.progress >= 0.2) return 2;
  return 1;
}

