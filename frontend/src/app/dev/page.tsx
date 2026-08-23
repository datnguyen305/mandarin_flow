"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, Cookie, KeyRound, Loader2, Play, Tag, Trash2, Upload, Youtube } from "lucide-react";
import { useRouter } from "next/navigation";
import { ImportChatbot } from "@/components/ImportChatbot";
import { ApiRequestError, deleteVideo, DevAccessError, getProcessingProgress, listVideos, NetworkRequestError, processVideo, uploadYouTubeCookies, verifyDevAccess } from "@/lib/api";
import { clearDevToken, readDevToken, writeDevToken } from "@/lib/devAuth";
import {
  IMPORT_PROCESSING_EVENT,
  createImportProcessingJob,
  friendlyProgressMessage,
  mergeServerProgress,
  readImportProcessingJob,
  removeImportProcessingJob,
  stepIndexForProgress,
  writeImportProcessingJob,
  type PersistedImportJob,
  type ProcessingUiState,
} from "@/lib/importProcessing";
import { extractYouTubeId } from "@/lib/subtitles";
import { formatVideoDuration } from "@/lib/videoCatalog";
import { getPreferredYouTubeThumbnail } from "@/lib/youtubeThumbnail";
import type { ImportedVideo, ProcessingProgress } from "@/types";

const processSteps = ["Tách ID", "Lấy phụ đề/ASR", "Dịch Việt", "Tách từ & Pinyin", "Lưu ngữ cảnh"];

function formatImportedDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function DevPage() {
  const router = useRouter();
  const redirectTimerRef = useRef<number | null>(null);
  const redirectOnCompleteRef = useRef(false);
  const [devToken, setDevToken] = useState<string | null>(() => readDevToken());
  const [tokenInput, setTokenInput] = useState("");
  const [url, setUrl] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [processingState, setProcessingState] = useState<ProcessingUiState>("idle");
  const [activeJob, setActiveJob] = useState<PersistedImportJob | null>(null);
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [cookies, setCookies] = useState("");
  const [cookiesStatus, setCookiesStatus] = useState<string | null>(null);
  const [cookiesLoading, setCookiesLoading] = useState(false);
  const [videos, setVideos] = useState<ImportedVideo[]>([]);
  const [videosLoading, setVideosLoading] = useState(false);
  const [deletingVideoId, setDeletingVideoId] = useState<string | null>(null);
  const [devLoginLoading, setDevLoginLoading] = useState(false);

  const refreshVideos = useCallback(async (token: string | null) => {
    if (!token) return;
    setVideosLoading(true);
    try {
      await verifyDevAccess(token);
      setVideos(await listVideos(100, token));
    } catch (exc) {
      if (exc instanceof DevAccessError) {
        clearDevToken();
        setDevToken(null);
        setError("Mã dev không hợp lệ hoặc đã được thay đổi. Vui lòng đăng nhập lại.");
        return;
      }
      setError(exc instanceof Error ? exc.message : "Không thể tải danh sách video dev.");
    } finally {
      setVideosLoading(false);
    }
  }, []);

  useEffect(() => {
    function syncProcessingJob() {
      const job = readImportProcessingJob();
      if (!job) {
        setActiveJob(null);
        setProgress(null);
        setError(null);
        setProcessingState((current) => current === "starting" ? current : "idle");
        redirectOnCompleteRef.current = false;
        return;
      }
      setActiveJob(job);
      setUrl(job.url);
      setProcessingState("processing");
    }

    syncProcessingJob();
    window.addEventListener(IMPORT_PROCESSING_EVENT, syncProcessingJob);
    return () => {
      window.removeEventListener(IMPORT_PROCESSING_EVENT, syncProcessingJob);
      if (redirectTimerRef.current != null) window.clearTimeout(redirectTimerRef.current);
    };
  }, [refreshVideos, router]);

  useEffect(() => {
    if (!devToken) return;
    const timer = window.setTimeout(() => refreshVideos(devToken), 0);
    return () => window.clearTimeout(timer);
  }, [devToken, refreshVideos]);

  useEffect(() => {
    const activeVideoId = activeJob?.videoId;
    if (!activeVideoId) return;
    const videoId: string = activeVideoId;
    let cancelled = false;
    let inFlight = false;
    let timer: number | null = null;
    let latestProgress: ProcessingProgress | null = null;

    function finishCompleted(nextProgress: ProcessingProgress) {
      const completedProgress = { ...nextProgress, status: "completed" as const, phase: "completed", progress: 1 };
      setProgress(completedProgress);
      setProcessingState("completed");
      setError(null);
      setActiveJob(null);
      removeImportProcessingJob(false);
      refreshVideos(readDevToken());
      if (redirectOnCompleteRef.current) {
        redirectOnCompleteRef.current = false;
        if (redirectTimerRef.current != null) window.clearTimeout(redirectTimerRef.current);
        redirectTimerRef.current = window.setTimeout(() => router.push(`/watch?v=${videoId}`), 450);
      }
    }

    function finishFailed(message: string, nextProgress?: ProcessingProgress) {
      if (nextProgress) setProgress(nextProgress);
      setProcessingState("failed");
      setError(message);
      redirectOnCompleteRef.current = false;
      setActiveJob(null);
      removeImportProcessingJob(false);
    }

    function clearMissingJob() {
      setActiveJob(null);
      setProgress(null);
      setError(null);
      setProcessingState("idle");
      redirectOnCompleteRef.current = false;
      removeImportProcessingJob(false);
    }

    async function poll() {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const serverProgress = await getProcessingProgress(videoId);
        if (cancelled) return;

        latestProgress = mergeServerProgress(latestProgress, serverProgress);
        const nextProgress = latestProgress;
        setProgress(nextProgress);

        if (nextProgress.status === "completed") {
          finishCompleted(nextProgress);
          return;
        }
        if (nextProgress.status === "failed") {
          finishFailed("Xử lý video bị lỗi. Bạn có thể thử import lại.", nextProgress);
          return;
        }
        setProcessingState("processing");
        setError(null);
      } catch (exc) {
        if (cancelled) return;
        if (exc instanceof ApiRequestError && exc.status === 404) {
          clearMissingJob();
          return;
        }
        if (!(exc instanceof NetworkRequestError)) {
          setError(exc instanceof Error ? exc.message : "Không thể theo dõi tiến trình xử lý.");
        }
      } finally {
        inFlight = false;
        if (!cancelled) {
          timer = window.setTimeout(poll, 2500);
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [activeJob?.videoId, refreshVideos, router]);

  function clearProcessingState() {
    if (redirectTimerRef.current != null) window.clearTimeout(redirectTimerRef.current);
    redirectOnCompleteRef.current = false;
    removeImportProcessingJob(false);
    setActiveJob(null);
    setProgress(null);
    setError(null);
    setProcessingState("cancelled");
  }

  async function handleDevLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = tokenInput.trim();
    if (!trimmed) return;
    setError(null);
    setDevLoginLoading(true);
    try {
      await verifyDevAccess(trimmed);
      writeDevToken(trimmed);
      setDevToken(trimmed);
      setTokenInput("");
    } catch (exc) {
      setError(exc instanceof DevAccessError ? "Mã dev không đúng." : exc instanceof Error ? exc.message : "Không thể xác thực mã dev.");
    } finally {
      setDevLoginLoading(false);
    }
  }

  function handleLogout() {
    clearDevToken();
    setDevToken(null);
    setVideos([]);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!devToken) return;
    if (redirectTimerRef.current != null) window.clearTimeout(redirectTimerRef.current);
    clearProcessingState();
    redirectOnCompleteRef.current = false;
    setError(null);
    setProgress(null);
    const localVideoId = extractYouTubeId(url);
    if (!localVideoId) {
      setError("Vui lòng dán một link YouTube hợp lệ.");
      return;
    }
    setActiveJob(null);
    setProcessingState("starting");
    redirectOnCompleteRef.current = true;
    try {
      const tags = Array.from(
        new Map(
          tagsInput
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean)
            .map((tag) => [tag.toLocaleLowerCase("vi"), tag])
        ).values()
      ).slice(0, 10);
      if (tags.some((tag) => /^https?:\/\//i.test(tag))) {
        setError("Chủ đề không được là đường dẫn. Hãy nhập chủ đề như Du lịch, Âm nhạc hoặc Hội thoại.");
        setProcessingState("idle");
        return;
      }
      const initialProgress = await processVideo(url, devToken, tags);
      const job = createImportProcessingJob(initialProgress.video_id, url);
      writeImportProcessingJob(job);
      setActiveJob(job);
      setProgress(initialProgress);
      if (initialProgress.status === "completed") {
        setProcessingState("completed");
        setActiveJob(null);
        removeImportProcessingJob(false);
        refreshVideos(devToken);
        redirectTimerRef.current = window.setTimeout(() => router.push(`/watch?v=${initialProgress.video_id}`), 450);
        return;
      }
      if (initialProgress.status === "failed") {
        setProcessingState("failed");
        setError("Xử lý video bị lỗi. Bạn có thể thử import lại.");
        setActiveJob(null);
        removeImportProcessingJob(false);
        return;
      }
      setProcessingState("processing");
    } catch (exc) {
      if (exc instanceof NetworkRequestError) {
        const job = createImportProcessingJob(localVideoId, url);
        writeImportProcessingJob(job);
        setActiveJob(job);
        setProcessingState("processing");
        setError(null);
        return;
      }
      const message = exc instanceof Error ? exc.message : "Không thể xử lý video.";
      redirectOnCompleteRef.current = false;
      setError(message);
      setProcessingState("failed");
    }
  }

  async function handleCookiesFile(file: File | null) {
    if (!file) return;
    setCookiesStatus(null);
    setCookies(await file.text());
  }

  async function handleCookiesSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!devToken) return;
    setCookiesStatus(null);
    setCookiesLoading(true);
    try {
      await uploadYouTubeCookies(cookies, devToken);
      setCookiesStatus("Đã lưu cookies YouTube.");
    } catch (exc) {
      setCookiesStatus(exc instanceof Error ? exc.message : "Không thể lưu cookies.");
    } finally {
      setCookiesLoading(false);
    }
  }

  async function handleDelete(video: ImportedVideo) {
    if (!devToken) return;
    const confirmed = window.confirm(`Xóa video "${video.title}" khỏi thư viện? Tất cả phụ đề và từ vựng đã lưu từ video này cũng sẽ bị xóa.`);
    if (!confirmed) return;

    setError(null);
    setDeletingVideoId(video.youtube_video_id);
    try {
      await deleteVideo(video.youtube_video_id, devToken);
      setVideos((current) => current.filter((item) => item.youtube_video_id !== video.youtube_video_id));
    } catch (exc) {
      if (exc instanceof DevAccessError) {
        clearDevToken();
        setDevToken(null);
        setError("Mã dev không hợp lệ hoặc đã được thay đổi. Vui lòng đăng nhập lại.");
        return;
      }
      setError(exc instanceof Error ? exc.message : "Không thể xóa video.");
    } finally {
      setDeletingVideoId(null);
    }
  }

  const isProcessing = processingState === "starting" || processingState === "processing";
  const progressPercent = Math.max(0, Math.min(100, Math.round((progress?.progress ?? 0) * 100)));
  const activeStepIndex = stepIndexForProgress(progress, processingState);
  const processingMessage = friendlyProgressMessage(progress, processingState);
  const progressLabel = progress
    ? progress.total_subtitles > 0
      ? `${progress.processed_subtitles}/${progress.total_subtitles} câu · ${progressPercent}%`
      : progress.total_batches > 0
        ? `${progress.processed_batches}/${progress.total_batches} phần · ${progressPercent}%`
        : `${progressPercent}%`
    : processingState === "starting"
      ? "Đang bắt đầu"
      : isProcessing
        ? "Đang kết nối"
        : "Chưa bắt đầu";
  const buttonLabel = isProcessing ? "Đang xử lý" : "Bắt đầu xử lý";
  const canResetTracking = processingState === "processing" || processingState === "starting";

  if (!devToken) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-57px)] max-w-md flex-col justify-center px-4 py-10">
        <form className="rounded-2xl border border-cream-200 bg-cream-50 p-5 shadow-sm" onSubmit={handleDevLogin}>
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-800">
              <KeyRound size={19} />
            </span>
            <div>
              <h1 className="text-lg font-semibold text-brand-900">Dev access</h1>
              <p className="text-sm text-slate-500">Nhập mã dev để import và quản lý video.</p>
            </div>
          </div>
          <input
            className="h-11 w-full rounded-xl border border-cream-300 bg-cream-100/50 px-3 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            placeholder="DEV_ACCESS_TOKEN"
            type="password"
            value={tokenInput}
            onChange={(event) => setTokenInput(event.target.value)}
          />
          {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
          <button className="mt-3 inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand-700 text-sm font-semibold text-cream-50 hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60" disabled={devLoginLoading} type="submit">
            {devLoginLoading ? <Loader2 className="animate-spin" size={17} /> : null}
            {devLoginLoading ? "Đang xác thực" : "Mở công cụ dev"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-brand-900">Dev workspace</h1>
          <p className="mt-1 text-sm text-slate-500">Import video, cập nhật cookies và quản lý thư viện.</p>
        </div>
        <button className="rounded-xl border border-cream-300 bg-cream-50 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-cream-100" onClick={handleLogout} type="button">
          Thoát dev
        </button>
      </div>

      <section className="rounded-2xl border border-cream-200 bg-cream-50 p-4 shadow-sm">
        <form className="rounded-2xl border border-cream-300 bg-cream-50 p-3 shadow-xl transition focus-within:border-brand-500" onSubmit={handleSubmit}>
          <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="youtube-url">
              Link YouTube
            </label>
            <div className="flex min-h-14 flex-1 items-center rounded-xl px-3">
              <Youtube className="mr-3 shrink-0 text-red-600" size={26} />
              <input
                className="w-full bg-transparent py-3 text-base text-slate-800 outline-none placeholder:text-slate-400"
                id="youtube-url"
                placeholder="Dán đường dẫn YouTube để import"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                required
              />
            </div>
            <button
              className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl bg-brand-700 px-7 text-base font-semibold text-cream-50 shadow-md transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isProcessing}
              type="submit"
            >
              {isProcessing ? <Loader2 className="animate-spin" size={19} /> : <Play size={19} />}
              {buttonLabel}
            </button>
          </div>
          <label className="mt-2 flex min-h-12 items-center gap-3 rounded-xl bg-cream-100/60 px-4 text-sm text-slate-600" htmlFor="video-tags">
            <Tag className="shrink-0 text-brand-700" size={18} />
            <span className="shrink-0 font-semibold text-slate-700">Chủ đề</span>
            <input
              className="w-full bg-transparent py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
              id="video-tags"
              placeholder="Không bắt buộc - ví dụ: Du lịch, Ẩm thực, Hội thoại"
              autoComplete="off"
              value={tagsInput}
              onChange={(event) => setTagsInput(event.target.value)}
            />
          </label>
          <div className="mt-3 overflow-hidden rounded-full bg-cream-200">
            <div
              className={`h-3 rounded-full transition-all duration-500 ${progress?.status === "failed" ? "bg-red-500" : "bg-brand-700"}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="mt-3 flex flex-col gap-1 px-1 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <span className="font-medium text-slate-600">{processingMessage}</span>
            <span className="flex items-center gap-3">
              <span>{progressLabel}</span>
              {canResetTracking ? (
                <button className="font-semibold text-slate-500 underline-offset-4 hover:text-brand-700 hover:underline" onClick={clearProcessingState} type="button">
                  Dừng theo dõi
                </button>
              ) : null}
            </span>
          </div>
          {error ? <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        </form>

        <div className="mt-4 rounded-xl border border-cream-200 bg-cream-100/60 p-4">
          <div className="grid gap-2 text-xs font-medium text-slate-500 sm:grid-cols-5">
            {processSteps.map((step, index) => (
              <div
                className={`flex items-center justify-center gap-2 rounded-lg px-2.5 py-2 ${
                  index <= activeStepIndex ? "bg-cream-50 font-semibold text-brand-700 shadow-sm" : "text-slate-500"
                }`}
                key={step}
              >
                {index <= activeStepIndex ? <CheckCircle2 size={16} className="text-brand-500" /> : <span className="h-2.5 w-2.5 rounded-full border border-slate-300" />}
                <span className="truncate">{step}</span>
              </div>
            ))}
          </div>
        </div>

        <details className="group mt-4 overflow-hidden rounded-xl border border-cream-200 bg-cream-50/70 transition">
          <summary className="flex cursor-pointer select-none items-center justify-between gap-3 p-4 text-sm font-semibold text-slate-600 hover:bg-cream-100/60">
            <span className="flex min-w-0 items-center gap-2">
              <Cookie size={18} className="shrink-0 text-amber-600" />
              <span className="truncate">Cấu hình cookies YouTube cho video hạn chế</span>
            </span>
            <ChevronDown size={18} className="shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
          </summary>

          <form className="space-y-4 border-t border-cream-200 bg-cream-50 p-5" onSubmit={handleCookiesSubmit}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-slate-500">Dán nội dung Netscape HTTP Cookie File nếu video yêu cầu đăng nhập.</p>
              <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-cream-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-cream-300">
                <Upload size={16} />
                Chọn file
                <input className="sr-only" type="file" accept=".txt,text/plain" onChange={(event) => handleCookiesFile(event.target.files?.[0] ?? null)} />
              </label>
            </div>
            <textarea
              className="min-h-32 w-full resize-y rounded-lg border border-cream-200 bg-cream-100/50 px-3 py-3 font-mono text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-brand-500"
              placeholder="# Netscape HTTP Cookie File..."
              value={cookies}
              onChange={(event) => setCookies(event.target.value)}
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {cookiesStatus ? <p className="rounded-lg border border-cream-200 bg-cream-100 px-3 py-2 text-sm text-slate-700">{cookiesStatus}</p> : <span />}
              <button
                className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg bg-slate-700 px-5 text-sm font-semibold text-cream-50 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={cookiesLoading || !cookies.trim()}
                type="submit"
              >
                {cookiesLoading ? <Loader2 className="animate-spin" size={17} /> : <Cookie size={17} />}
                Lưu cookies
              </button>
            </div>
          </form>
        </details>
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-brand-900">Video trong hệ thống</h2>
          <button className="rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-cream-100" onClick={() => refreshVideos(devToken)} type="button">
            Làm mới
          </button>
        </div>
        {videosLoading ? (
          <div className="flex min-h-32 items-center justify-center gap-2 rounded-2xl border border-cream-200 bg-cream-50 text-sm text-slate-600">
            <Loader2 className="animate-spin text-brand-700" size={18} />
            Đang tải video...
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {videos.map((video) => (
              <article className="overflow-hidden rounded-2xl border border-cream-200 bg-cream-50 shadow-sm" key={video.id}>
                <Link href={`/watch?v=${video.youtube_video_id}`} className="block">
                  <div className="relative aspect-video bg-slate-900">
                    {video.thumbnail_url ? (
                      <Image
                        alt={video.title}
                        className="object-cover"
                        fill
                        onError={(event) => {
                          if (event.currentTarget.src !== video.thumbnail_url) event.currentTarget.src = video.thumbnail_url ?? "";
                        }}
                        quality={95}
                        sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                        src={getPreferredYouTubeThumbnail(video.youtube_video_id, video.thumbnail_url) ?? video.thumbnail_url}
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center font-serif text-5xl font-bold text-cream-50">汉</div>
                    )}
                  </div>
                </Link>
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    <Link className="line-clamp-2 min-h-11 flex-1 font-semibold leading-snug text-slate-800 hover:text-brand-700" href={`/watch?v=${video.youtube_video_id}`}>
                      {video.title}
                    </Link>
                    <button
                      aria-label={`Xóa video ${video.title}`}
                      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={deletingVideoId === video.youtube_video_id}
                      onClick={() => handleDelete(video)}
                      type="button"
                    >
                      {deletingVideoId === video.youtube_video_id ? <Loader2 className="animate-spin" size={15} /> : <Trash2 size={15} />}
                    </button>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
                    <span>{formatImportedDate(video.created_at)}</span>
                    <span className="rounded-full bg-brand-100 px-2 py-1 font-medium text-brand-800">{video.processing_status}</span>
                  </div>
                  {video.tags.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {video.tags.map((tag) => (
                        <span className="rounded-full bg-cream-100 px-2 py-1 text-xs font-medium text-slate-600" key={tag}>{tag}</span>
                      ))}
                    </div>
                  ) : null}
                  {formatVideoDuration(video.duration_seconds) ? (
                    <div className="mt-2 text-xs font-medium text-slate-500">
                      Thời lượng: {formatVideoDuration(video.duration_seconds)}
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      {devToken ? <ImportChatbot devToken={devToken} /> : null}
    </main>
  );
}
