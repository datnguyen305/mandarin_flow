"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertCircle, CheckCircle2, ExternalLink, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";
import {
  IMPORT_PROCESSING_EVENT,
  progressMessage,
  readImportProcessingTask,
  removeImportProcessingTask,
  writeImportProcessingTask,
  type ImportProcessingTask,
} from "@/lib/importProcessing";
import type { ProcessingProgress } from "@/types";

export function ImportProcessingMonitor() {
  const pathname = usePathname();
  const eventSourceRef = useRef<EventSource | null>(null);
  const eventSourceVideoRef = useRef<string | null>(null);
  const taskRef = useRef<ImportProcessingTask | null>(null);
  const [task, setTask] = useState<ImportProcessingTask | null>(null);

  useEffect(() => {
    taskRef.current = task;
  }, [task]);

  const taskVideoId = task?.videoId;
  const taskStatus = task?.progress.status;

  useEffect(() => {
    function sync() {
      setTask(readImportProcessingTask());
    }

    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(IMPORT_PROCESSING_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(IMPORT_PROCESSING_EVENT, sync);
    };
  }, []);

  useEffect(() => {
    const initialTask = taskRef.current;
    if (!initialTask || taskStatus === "completed" || taskStatus === "failed") {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      eventSourceVideoRef.current = null;
      return;
    }

    if (!taskVideoId) return;
    if (eventSourceRef.current && eventSourceVideoRef.current === taskVideoId) return;

    eventSourceRef.current?.close();
    const eventSource = new EventSource(`${API_BASE_URL}/api/videos/${encodeURIComponent(taskVideoId)}/subtitles/stream`);
    eventSourceRef.current = eventSource;
    eventSourceVideoRef.current = taskVideoId;

    eventSource.addEventListener("processing_progress", (streamEvent) => {
      const nextProgress = JSON.parse((streamEvent as MessageEvent).data) as ProcessingProgress;
      const currentTask = taskRef.current;
      if (!currentTask) return;
      writeImportProcessingTask({
        ...currentTask,
        progress: nextProgress,
        message: progressMessage(nextProgress),
        error: null,
        updatedAt: Date.now(),
      });
    });

    eventSource.addEventListener("processing_completed", () => {
      const currentTask = taskRef.current;
      if (!currentTask) return;
      const completedProgress: ProcessingProgress = {
        ...currentTask.progress,
        status: "completed",
        processed_batches: currentTask.progress.total_batches,
        processed_subtitles: currentTask.progress.total_subtitles,
        progress: 1,
      };
      writeImportProcessingTask({
        ...currentTask,
        progress: completedProgress,
        message: "Đã xử lý xong.",
        error: null,
        updatedAt: Date.now(),
      });
      eventSource.close();
      eventSourceRef.current = null;
      eventSourceVideoRef.current = null;
    });

    eventSource.addEventListener("processing_failed", (streamEvent) => {
      const data = JSON.parse((streamEvent as MessageEvent).data) as { batch_index?: number; message?: string };
      const currentTask = taskRef.current;
      if (!currentTask) return;
      writeImportProcessingTask({
        ...currentTask,
        progress: { ...currentTask.progress, status: "failed" },
        message: "Xử lý bị dừng.",
        error: `Một batch phụ đề bị lỗi${data.batch_index != null ? ` (#${data.batch_index})` : ""}: ${data.message ?? "vui lòng thử lại"}`,
        updatedAt: Date.now(),
      });
      eventSource.close();
      eventSourceRef.current = null;
      eventSourceVideoRef.current = null;
    });

    eventSource.onerror = () => {
      const currentTask = taskRef.current;
      if (!currentTask) return;
      writeImportProcessingTask({
        ...currentTask,
        progress: { ...currentTask.progress, status: "failed" },
        message: "Mất kết nối tiến trình xử lý.",
        error: "Không thể theo dõi tiến trình xử lý. Quay lại trang Import để thử lại.",
        updatedAt: Date.now(),
      });
      eventSource.close();
      eventSourceRef.current = null;
      eventSourceVideoRef.current = null;
    };

    return () => {
      eventSource.close();
      if (eventSourceRef.current === eventSource) {
        eventSourceRef.current = null;
        eventSourceVideoRef.current = null;
      }
    };
  }, [taskStatus, taskVideoId]);

  if (!task || pathname === "/") return null;

  const percent = Math.max(0, Math.min(100, Math.round(task.progress.progress * 100)));
  const isCompleted = task.progress.status === "completed";
  const isFailed = task.progress.status === "failed";

  return (
    <aside className="fixed bottom-3 left-3 z-40 w-[min(420px,calc(100vw-24px))] rounded-lg border border-cream-200 bg-cream-50 p-3 shadow-2xl">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-brand-900">
            {isFailed ? <AlertCircle size={16} className="text-red-600" /> : isCompleted ? <CheckCircle2 size={16} className="text-brand-600" /> : <Loader2 size={16} className="animate-spin text-brand-700" />}
            <span className="truncate">{task.message}</span>
          </div>
          <p className="mt-1 truncate text-xs text-slate-500">
            {task.progress.processed_batches}/{task.progress.total_batches || 0} batch - {task.progress.processed_subtitles}/{task.progress.total_subtitles || 0} dòng phụ đề
          </p>
        </div>
        {(isCompleted || isFailed) && (
          <button aria-label="Ẩn tiến trình import" className="rounded-md p-1 text-slate-500 hover:bg-cream-100" onClick={removeImportProcessingTask} type="button">
            <X size={15} />
          </button>
        )}
      </div>
      <div className="mt-3 overflow-hidden rounded-full bg-cream-200">
        <div className={`h-2 rounded-full transition-all duration-500 ${isFailed ? "bg-red-500" : "bg-brand-700"}`} style={{ width: `${percent}%` }} />
      </div>
      {task.error ? <p className="mt-2 text-xs leading-5 text-red-700">{task.error}</p> : null}
      {isCompleted ? (
        <Link className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-800 hover:text-brand-900" href={`/watch?v=${encodeURIComponent(task.videoId)}`}>
          <ExternalLink size={14} />
          Mở video đã xử lý
        </Link>
      ) : null}
    </aside>
  );
}
