"use client";

import { Suspense, useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BookOpen, ChevronLeft, ChevronRight, Clock, Loader2, Search, RotateCcw, Languages } from "lucide-react";
import { DictionaryPanel } from "@/components/DictionaryPanel";
import { MobileWordMeaningPopup } from "@/components/MobileWordMeaningPopup";
import { YouTubePlayer, type YouTubePlayerHandle } from "@/components/YouTubePlayer";
import { API_BASE_URL, getRawSubtitles, listVocabulary, lookupWord, saveVocabulary, updatePlaybackPosition } from "@/lib/api";
import { countWordsSavedToday, notifyLearningProgress } from "@/lib/learningProgress";
import { findActiveSubtitleIndex, formatTimestamp, mergeSubtitleBatch } from "@/lib/subtitles";
import { convertChineseText, type ChineseScript } from "@/lib/chinese-script";
import type { DictionaryEntry, SubtitleBatch, SubtitleLine, SubtitleToken } from "@/types";

const LAST_WATCH_HREF_KEY = "fluentmandarin:last-watch-href";
const FLOATING_VIDEO_HIDDEN_KEY = "fluentmandarin:floating-video-hidden";
const SUBTITLE_SCRIPT_KEY = "fluentmandarin:subtitle-script";
const WATCH_LAYOUT_KEY = "mandarinflow:watch-layout";

const DEFAULT_WATCH_LAYOUT: WatchLayout = {
  leftWidth: 52,
  videoHeight: 58,
};

interface WatchLayout {
  leftWidth: number;
  videoHeight: number;
}

type ResizeAxis = "vertical" | "horizontal";

function WatchContent() {
  const searchParams = useSearchParams();
  const videoId = searchParams.get("v") ?? "";
  const startTime = Number(searchParams.get("t") ?? 0);
  const playerRef = useRef<YouTubePlayerHandle | null>(null);
  const workspaceRef = useRef<HTMLElement | null>(null);
  const leftColumnRef = useRef<HTMLElement | null>(null);
  const layoutRef = useRef<WatchLayout>(DEFAULT_WATCH_LAYOUT);
  const [subtitles, setSubtitles] = useState<SubtitleLine[]>([]);
  const [title, setTitle] = useState<string>("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [selectedToken, setSelectedToken] = useState<SubtitleToken | null>(null);
  const [dictionaryEntry, setDictionaryEntry] = useState<DictionaryEntry | null>(null);
  const [dictionaryLoading, setDictionaryLoading] = useState(false);
  const [dictionaryError, setDictionaryError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [selectedSubtitle, setSelectedSubtitle] = useState<SubtitleLine | null>(null);
  const [sidebarTab, setSidebarTab] = useState<"words" | "transcript">("words");
  const [subtitleScript, setSubtitleScript] = useState<ChineseScript>("simplified");
  const [watchLayout, setWatchLayout] = useState<WatchLayout>(DEFAULT_WATCH_LAYOUT);
  const lastPlaybackPostRef = useRef({ time: -1, sentAt: 0 });
  const transcriptItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const transcriptPanelRef = useRef<HTMLDivElement | null>(null);
  const sidebarPanelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const savedScript = window.localStorage.getItem(SUBTITLE_SCRIPT_KEY);
    if (savedScript !== "simplified" && savedScript !== "traditional") return;
    const timer = window.setTimeout(() => setSubtitleScript(savedScript), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const saved = readWatchLayout();
    layoutRef.current = saved;
    workspaceRef.current?.style.setProperty("--watch-left-width", `${saved.leftWidth}%`);
    workspaceRef.current?.style.setProperty("--watch-video-height", `${saved.videoHeight}%`);
    const timer = window.setTimeout(() => setWatchLayout(saved), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    document.documentElement.classList.add("max-h-screen", "overflow-hidden");
    document.body.classList.add("max-h-screen", "overflow-hidden");
    return () => {
      document.documentElement.classList.remove("max-h-screen", "overflow-hidden");
      document.body.classList.remove("max-h-screen", "overflow-hidden");
    };
  }, []);

  function handleScriptChange(script: ChineseScript) {
    setSubtitleScript(script);
    window.localStorage.setItem(SUBTITLE_SCRIPT_KEY, script);
  }

  function applyWatchLayout(next: WatchLayout) {
    layoutRef.current = next;
    workspaceRef.current?.style.setProperty("--watch-left-width", `${next.leftWidth}%`);
    workspaceRef.current?.style.setProperty("--watch-video-height", `${next.videoHeight}%`);
  }

  function persistWatchLayout() {
    const next = layoutRef.current;
    setWatchLayout(next);
    window.localStorage.setItem(WATCH_LAYOUT_KEY, JSON.stringify(next));
  }

  function resetWatchLayout() {
    applyWatchLayout(DEFAULT_WATCH_LAYOUT);
    persistWatchLayout();
  }

  function nudgeResize(axis: ResizeAxis, delta: number) {
    const current = layoutRef.current;
    const next = axis === "vertical"
      ? { ...current, leftWidth: clamp(current.leftWidth + delta, 40, 70) }
      : { ...current, videoHeight: clamp(current.videoHeight + delta, 35, 75) };
    applyWatchLayout(next);
    persistWatchLayout();
  }

  function beginResize(event: ReactPointerEvent<HTMLDivElement>) {
    if (window.matchMedia("(max-width: 1023px)").matches) return;
    event.preventDefault();
    const startLayout = { ...layoutRef.current };
    const workspace = workspaceRef.current;
    const leftColumn = leftColumnRef.current;
    if (!workspace || !leftColumn) return;

    const workspaceRect = workspace.getBoundingClientRect();
    const leftRect = leftColumn?.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const previousUserSelect = document.body.style.userSelect;
    const previousCursor = document.body.style.cursor;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";

    function handlePointerMove(moveEvent: PointerEvent) {
      if (!leftRect) return;
      const horizontalDelta = ((moveEvent.clientX - startX) / workspaceRect.width) * 100;
      const verticalDelta = ((moveEvent.clientY - startY) / leftRect.height) * 100;
      applyWatchLayout({
        leftWidth: clamp(startLayout.leftWidth + horizontalDelta, 40, 70),
        videoHeight: clamp(startLayout.videoHeight + verticalDelta, 35, 75),
      });
    }

    function finishResize() {
      document.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("pointerup", finishResize);
      document.body.style.userSelect = previousUserSelect;
      document.body.style.cursor = previousCursor;
      persistWatchLayout();
    }

    document.addEventListener("pointermove", handlePointerMove);
    document.addEventListener("pointerup", finishResize, { once: true });
  }

  function beginMobileResize(event: ReactPointerEvent<HTMLDivElement>) {
    if (window.matchMedia("(min-width: 768px)").matches) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const leftColumn = leftColumnRef.current;
    if (!leftColumn) return;

    const rect = leftColumn.getBoundingClientRect();
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.userSelect = "none";

    function handlePointerMove(moveEvent: PointerEvent) {
      const videoHeight = ((moveEvent.clientY - rect.top) / rect.height) * 100;
      applyWatchLayout({ ...layoutRef.current, videoHeight: clamp(videoHeight, 32, 68) });
    }

    function finishResize() {
      document.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("pointerup", finishResize);
      document.body.style.userSelect = previousUserSelect;
      persistWatchLayout();
    }

    document.addEventListener("pointermove", handlePointerMove);
    document.addEventListener("pointerup", finishResize, { once: true });
  }

  useEffect(() => {
    if (!videoId) return;
    saveLastWatchHref(videoId);
    let eventSource: EventSource | null = null;
    let cancelled = false;

    function openSubtitleStream() {
      eventSource = new EventSource(`${API_BASE_URL}/api/videos/${encodeURIComponent(videoId)}/subtitles/stream`, { withCredentials: true });
      eventSource.addEventListener("subtitle_batch", (event) => {
        const batch = JSON.parse((event as MessageEvent).data) as SubtitleBatch;
        setSubtitles((current) => mergeSubtitleBatch(current, batch));
      });
      eventSource.addEventListener("processing_completed", () => {
        eventSource?.close();
      });
      eventSource.addEventListener("processing_failed", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { batch_index?: number; message?: string };
        setError(`Một batch phụ đề bị lỗi${data.batch_index != null ? ` (#${data.batch_index})` : ""}: ${data.message ?? "có thể retry sau"}`);
      });
      eventSource.onerror = () => {
        if (!cancelled) setError("Mất kết nối stream phụ đề. Refresh trang để đồng bộ lại các batch đã xử lý.");
      };
    }

    async function loadSubtitles() {
      setError(null);
      setLoading(true);
      try {
        const data = await getRawSubtitles(videoId);
        if (cancelled) return;
        setSubtitles(data.subtitles);
        setTitle(data.title ?? videoId);
        if (!hasCompletedSubtitles(data.subtitles)) openSubtitleStream();
      } catch (exc) {
        if (!cancelled) {
          setTitle(videoId);
          setError(exc instanceof Error ? exc.message : "Video này chưa được chuẩn bị.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSubtitles();
    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [videoId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const currentTime = playerRef.current?.getCurrentTime() ?? 0;
      setActiveIndex(findActiveSubtitleIndex(subtitles, currentTime));
      if (videoId) saveLastWatchHref(videoId, currentTime);

      const now = Date.now();
      const last = lastPlaybackPostRef.current;
      const jumped = Math.abs(currentTime - last.time) > 20;
      const stale = now - last.sentAt > 8000;
      if (videoId && (jumped || stale)) {
        lastPlaybackPostRef.current = { time: currentTime, sentAt: now };
        updatePlaybackPosition(videoId, currentTime).catch(() => undefined);
      }
    }, 300);
    return () => window.clearInterval(timer);
  }, [subtitles, videoId]);

  const activeSubtitle = activeIndex >= 0 ? subtitles[activeIndex] : null;
  const activeVietnameseText = activeSubtitle ? getVietnameseText(activeSubtitle) : null;

  useEffect(() => {
    if (sidebarTab !== "transcript" || !activeSubtitle) return;
    const panel = transcriptPanelRef.current;
    const item = transcriptItemRefs.current.get(subtitleDomKey(activeSubtitle));
    if (!panel || !item) return;

    const itemCenter = item.offsetTop + item.offsetHeight / 2;
    const targetTop = Math.max(0, itemCenter - panel.clientHeight / 2);
    panel.scrollTo({ top: targetTop, behavior: "smooth" });
  }, [activeSubtitle, sidebarTab]);

  async function handleTokenClick(token: SubtitleToken, subtitle: SubtitleLine) {
    setSelectedToken(token);
    setSelectedSubtitle(subtitle);
    setDictionaryEntry(null);
    setDictionaryError(null);
    setSaveStatus(null);
    if (!token.text) return;
    setDictionaryLoading(true);
    try {
      const entry = await lookupWord(token.text, subtitle.text, token.pinyin);
      setDictionaryEntry(entry);
    } catch (exc) {
      setDictionaryError(exc instanceof Error ? exc.message : "Không thể tra từ này.");
    } finally {
      setDictionaryLoading(false);
    }
  }

  function navigateSubtitle(direction: -1 | 1) {
    const currentIndex = activeIndex >= 0 ? activeIndex : direction > 0 ? -1 : 0;
    const targetIndex = currentIndex + direction;
    const targetSubtitle = subtitles[targetIndex];
    if (!targetSubtitle) return;

    setSelectedToken(null);
    setSelectedSubtitle(null);
    setDictionaryEntry(null);
    setSaveStatus(null);
    setActiveIndex(targetIndex);
    playerRef.current?.seekTo(targetSubtitle.start);
  }

  async function handleSave() {
    const sourceSubtitle = selectedSubtitle ?? activeSubtitle;
    if (!selectedToken || !sourceSubtitle?.id) return;
    setSaving(true);
    try {
      const saveResult = await saveVocabulary({
        word: selectedToken.text,
        pinyin: dictionaryEntry?.pinyin ?? selectedToken.pinyin,
        meaning: dictionaryEntry?.meaning ?? selectedToken.meaning,
        youtube_video_id: videoId,
        subtitle_id: sourceSubtitle.id,
        timestamp: sourceSubtitle.start
      });
      if (saveResult.status === "already_saved") {
        setSaveStatus("Từ này đã được lưu rồi");
        return;
      }
      const vocabularyItems = await listVocabulary();
      notifyLearningProgress(vocabularyItems.length, true, countWordsSavedToday(vocabularyItems));
      setSaveStatus("Đã lưu vào sổ từ vựng");
    } catch (exc) {
      setSaveStatus(exc instanceof Error ? exc.message : "Không thể lưu từ này");
    } finally {
      setSaving(false);
    }
  }

  if (!videoId) {
    return <main className="mx-auto max-w-4xl px-4 py-10 text-red-600">Thiếu YouTube video ID.</main>;
  }

  return (
    <main
      className="relative mx-auto grid h-[calc(100dvh-116px)] max-h-[calc(100dvh-116px)] max-w-[1600px] grid-cols-1 gap-3 overflow-y-auto px-3 py-2 sm:h-[calc(100dvh-61px)] sm:max-h-[calc(100dvh-61px)] lg:grid-cols-[minmax(0,var(--watch-left-width))_minmax(0,1fr)] lg:gap-2 lg:overflow-hidden"
      ref={workspaceRef}
      style={{
        "--watch-left-width": `${watchLayout.leftWidth}%`,
        "--watch-video-height": `${watchLayout.videoHeight}%`,
      } as CSSProperties}
    >
      <section
        className="relative grid min-h-0 grid-rows-[minmax(0,var(--watch-video-height))_minmax(0,1fr)] gap-3 overflow-hidden lg:gap-2"
        ref={leftColumnRef}
      >
        <div className="flex min-h-0 w-full flex-col overflow-hidden rounded-xl border border-cream-200 bg-cream-50 shadow-lg">
          <div className="flex min-h-0 flex-1 items-center justify-center bg-black">
            <div className="aspect-video h-full w-auto max-w-full">
              <YouTubePlayer ref={playerRef} videoId={videoId} startTime={startTime} />
            </div>
          </div>
          <div className="flex h-10 shrink-0 items-center justify-between gap-2 border-t border-cream-200 px-2.5">
            <div className="min-w-0">
              <h1 className="truncate text-xs font-semibold leading-tight text-brand-900 sm:text-sm">{title || videoId}</h1>
            </div>
            <div className="flex shrink-0 gap-1.5">
              <Link className="inline-flex h-7 items-center gap-1 rounded-md border border-cream-300 bg-cream-100 px-2 text-[11px] text-slate-700 hover:bg-cream-200" href="/">
                <ArrowLeft size={13} />
                Danh sách
              </Link>
              {activeSubtitle ? (
                <button
                  className="inline-flex h-7 items-center gap-1 rounded-md border border-cream-300 bg-cream-100 px-2 text-[11px] text-slate-700 hover:bg-cream-200"
                  onClick={() => playerRef.current?.seekTo(activeSubtitle.start)}
                >
                  <RotateCcw size={13} />
                  Replay
                </button>
              ) : null}
              <button
                aria-label="Đặt lại kích thước layout"
                className="inline-flex h-7 items-center gap-1 rounded-md border border-cream-300 bg-cream-100 px-2 text-[11px] text-slate-700 hover:bg-cream-200"
                onClick={resetWatchLayout}
                title="Đặt lại kích thước layout"
                type="button"
              >
                <RotateCcw size={13} />
                Layout
              </button>
              <Link className="hidden h-7 items-center gap-1 rounded-md bg-brand-700 px-2 text-[11px] font-semibold text-cream-50 hover:bg-brand-800 sm:inline-flex" href="/vocabulary">
                <BookOpen size={13} />
                Wordbank
              </Link>
            </div>
          </div>
        </div>
        <div className="relative flex min-h-0 max-h-full flex-col overflow-hidden rounded-xl border border-cream-200 bg-cream-50 p-3 text-center shadow-sm">
            <div className="mb-3 flex shrink-0 items-center justify-between">
            <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-700">
              <span className="h-2 w-2 rounded-full bg-brand-500" />
              Phụ đề tương tác
            </span>
            <div className="flex items-center gap-2">
              <div className="inline-flex items-center gap-0.5 rounded-lg border border-cream-300 bg-cream-100 p-0.5 md:hidden" aria-label="Chọn câu phụ đề">
                <button
                  aria-label="Câu phụ đề trước"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-600 transition hover:bg-cream-50 hover:text-brand-800 disabled:cursor-not-allowed disabled:opacity-35"
                  disabled={activeIndex <= 0}
                  onClick={() => navigateSubtitle(-1)}
                  type="button"
                >
                  <ChevronLeft size={17} />
                </button>
                <button
                  aria-label="Câu phụ đề sau"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-600 transition hover:bg-cream-50 hover:text-brand-800 disabled:cursor-not-allowed disabled:opacity-35"
                  disabled={subtitles.length === 0 || activeIndex >= subtitles.length - 1}
                  onClick={() => navigateSubtitle(1)}
                  type="button"
                >
                  <ChevronRight size={17} />
                </button>
              </div>
              <span className="hidden text-[11px] text-slate-400 sm:inline">Bấm từ để xem nghĩa</span>
              <div className="inline-flex items-center gap-0.5 rounded-lg border border-cream-300 bg-cream-100 p-0.5" aria-label="Chọn dạng chữ phụ đề">
                <Languages size={14} className="mx-1 text-slate-500" />
                {(["simplified", "traditional"] as ChineseScript[]).map((script) => (
                  <button
                    className={`rounded-md px-2 py-1 text-[11px] font-semibold transition ${subtitleScript === script ? "bg-cream-50 text-brand-800 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                    key={script}
                    onClick={() => handleScriptChange(script)}
                    type="button"
                  >
                    {script === "simplified" ? "简体" : "繁體"}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-slate-600">
              <Loader2 className="animate-spin text-brand-700" size={22} />
              <p className="text-sm">Video có thể phát ngay. Phụ đề đang được xử lý theo từng batch...</p>
            </div>
          ) : null}
          {error ? (
            <div className="mx-auto max-w-xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-left text-sm text-red-700">
              {error}
            </div>
          ) : null}
          {!loading && !error && !activeSubtitle ? (
            <div className="flex min-h-40 flex-col items-center justify-center text-slate-500">
              <Search size={24} />
              <p className="mt-3 text-sm">Đang chờ dòng phụ đề tiếp theo.</p>
            </div>
          ) : null}
          {activeSubtitle ? (
            <>
              <div className="mb-3 inline-flex items-center gap-2 rounded-xl bg-cream-200 px-2.5 py-1 text-xs font-medium text-slate-600">
                <Clock size={14} />
                {formatTimestamp(activeSubtitle.start)}
              </div>
              <p className="mt-2 font-serif text-2xl font-bold leading-relaxed tracking-wide text-slate-800 xl:text-3xl">{convertChineseText(activeSubtitle.text, subtitleScript)}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600 xl:text-base">
                {activeSubtitle.processing_status === "failed" ? "Batch này xử lý lỗi. Có thể retry sau." : activeVietnameseText}
              </p>
              {(activeSubtitle.tokens ?? []).length > 0 ? (
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {(activeSubtitle.tokens ?? []).map((token, index) => (
                  <button
                    className={`flex min-w-14 flex-col items-center rounded-lg border px-2.5 py-1.5 transition ${
                      selectedToken?.text === token.text
                        ? "border-brand-200 bg-brand-100 text-brand-900"
                        : "border-transparent text-slate-800 hover:border-brand-200 hover:bg-brand-100 hover:text-brand-900"
                    }`}
                    key={`${token.text}-${index}`}
                    onClick={() => handleTokenClick(token, activeSubtitle)}
                  >
                    <span className="font-mono text-xs leading-4 text-brand-700">{token.pinyin}</span>
                    <span className="font-serif text-xl leading-7">{convertChineseText(token.text, subtitleScript)}</span>
                  </button>
                  ))}
                </div>
              ) : (
                <p className="mt-5 text-sm text-slate-500">Đang tách từ...</p>
              )}
            </>
          ) : null}
          </div>
        </div>
        <div
          aria-label="Điều chỉnh kích thước video và phụ đề"
          aria-orientation="horizontal"
          aria-valuemax={68}
          aria-valuemin={32}
          aria-valuenow={watchLayout.videoHeight}
          className="absolute inset-x-0 z-20 flex h-5 -translate-y-1/2 touch-none cursor-row-resize items-center justify-center md:hidden"
          onKeyDown={(event) => {
            if (event.key === "ArrowUp") nudgeResize("horizontal", -2);
            if (event.key === "ArrowDown") nudgeResize("horizontal", 2);
          }}
          onPointerDown={beginMobileResize}
          role="separator"
          style={{ top: `var(--watch-video-height)` }}
          tabIndex={0}
          title="Kéo để thay đổi kích thước video và phụ đề"
        >
          <span className="h-1.5 w-14 rounded-full border border-cream-300 bg-cream-50 shadow-sm" />
        </div>
      </section>

      <section className="hidden min-h-0 overflow-hidden md:block">
        <aside className="flex h-full min-h-0 max-h-full flex-col overflow-hidden rounded-xl border border-cream-200 bg-cream-50 shadow-sm" ref={sidebarPanelRef}>
        <div className="shrink-0 border-b border-cream-200 bg-cream-100/70 p-2">
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-cream-200/70 p-1 text-sm">
            <button
              className={`rounded-lg py-1.5 font-semibold ${sidebarTab === "transcript" ? "bg-cream-50 text-brand-800 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
              onClick={() => setSidebarTab("transcript")}
            >
              Phụ đề
            </button>
            <button
              className={`rounded-lg py-1.5 font-semibold ${sidebarTab === "words" ? "bg-cream-50 text-brand-800 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
              onClick={() => setSidebarTab("words")}
            >
              Từ trong câu
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3" ref={transcriptPanelRef}>
          {sidebarTab === "words" ? (
            <div className="space-y-2">
              {(activeSubtitle?.tokens ?? []).map((token, index) => (
                <button
                  className={`flex w-full items-center justify-between rounded-xl border p-2.5 text-left transition ${
                    selectedToken?.text === token.text ? "border-brand-200 bg-brand-50" : "border-cream-200 bg-cream-100/50 hover:bg-cream-100"
                  }`}
                  key={`${token.text}-side-${index}`}
                  onClick={() => activeSubtitle && handleTokenClick(token, activeSubtitle)}
                >
                  <span className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 font-serif text-base font-bold text-brand-800">
                      {convertChineseText(token.text, subtitleScript).slice(0, 1)}
                    </span>
                    <span>
                      <span className="block font-serif text-base font-bold text-slate-800">{convertChineseText(token.text, subtitleScript)}</span>
                      <span className="block text-sm font-mono text-brand-700">{token.pinyin}</span>
                    </span>
                  </span>
                  <span className="max-w-40 truncate text-sm text-slate-500">{token.meaning || "Bấm để tra"}</span>
                </button>
              ))}
              {!activeSubtitle ? <p className="py-8 text-center text-base text-slate-500">Chưa có dòng phụ đề đang phát.</p> : null}
            </div>
          ) : (
            <div className="space-y-2">
              {subtitles.map((subtitle) => (
                <button
                  className={`w-full rounded-xl border px-2.5 py-2 text-left transition ${
                    subtitle === activeSubtitle ? "border-brand-200 bg-brand-50" : "border-cream-200 bg-cream-100/50 hover:bg-cream-100"
                  }`}
                  key={`${subtitle.start}-side-${subtitle.text}`}
                  onClick={() => playerRef.current?.seekTo(subtitle.start)}
                  ref={(element) => {
                    const key = subtitleDomKey(subtitle);
                    if (element) {
                      transcriptItemRefs.current.set(key, element);
                    } else {
                      transcriptItemRefs.current.delete(key);
                    }
                  }}
                >
                  <span className="block text-xs font-medium text-slate-400">{formatTimestamp(subtitle.start)}</span>
                  <span className="mt-1 block font-serif text-base font-semibold text-slate-800">{convertChineseText(subtitle.text, subtitleScript)}</span>
                  <span className="mt-1 block text-sm leading-6 text-slate-600">{getVietnameseText(subtitle)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0 border-t border-cream-200 bg-cream-100/70 p-3">
          <div className="flex items-center justify-between text-sm text-slate-500">
            <span>Dòng phụ đề</span>
            <strong className="text-brand-800">{subtitles.length}</strong>
          </div>
        </div>
        </aside>
      </section>
      <div className="pointer-events-none absolute inset-x-3 bottom-2 top-2 z-20 hidden lg:block">
        <div
          aria-label="Điều chỉnh kích thước ba khu vực video"
          aria-orientation="vertical"
          aria-valuemax={70}
          aria-valuemin={40}
          aria-valuenow={watchLayout.leftWidth}
          className="pointer-events-auto absolute h-12 w-3 -translate-x-1/2 -translate-y-1/2 cursor-col-resize touch-none rounded-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
          onDoubleClick={resetWatchLayout}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") nudgeResize("vertical", -2);
            if (event.key === "ArrowRight") nudgeResize("vertical", 2);
            if (event.key === "ArrowUp") nudgeResize("horizontal", -2);
            if (event.key === "ArrowDown") nudgeResize("horizontal", 2);
          }}
          onPointerDown={beginResize}
          role="separator"
          style={{ left: `calc(${watchLayout.leftWidth}% + 4px)`, top: `calc(${watchLayout.videoHeight}% + 4px)` }}
          tabIndex={0}
          title="Kéo điểm giữa để điều chỉnh cả ba khu vực"
        >
        </div>
      </div>
      {selectedToken ? (
        <>
          <MobileWordMeaningPopup
            entry={dictionaryEntry}
            error={dictionaryError}
            loading={dictionaryLoading}
            onClose={() => {
              setSelectedToken(null);
              setDictionaryError(null);
            }}
            onSave={handleSave}
            saveStatus={saveStatus}
            saving={saving}
            script={subtitleScript}
            token={selectedToken}
          />
          <div className="hidden md:block">
            <DictionaryPanel
              token={selectedToken}
              entry={dictionaryEntry}
              loading={dictionaryLoading}
              error={dictionaryError}
              subtitle={selectedSubtitle ?? activeSubtitle}
              saving={saving}
              onClose={() => {
                setSelectedToken(null);
                setDictionaryError(null);
              }}
              onPause={() => playerRef.current?.pause()}
              onSave={handleSave}
              saveStatus={saveStatus}
              script={subtitleScript}
              anchorRef={sidebarPanelRef}
            />
          </div>
        </>
      ) : null}
    </main>
  );
}

function saveLastWatchHref(videoId: string, currentTime = 0) {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams({ v: videoId });
  if (currentTime > 1) params.set("t", String(Math.floor(currentTime)));
  window.localStorage.setItem(LAST_WATCH_HREF_KEY, `/watch?${params.toString()}`);
  window.localStorage.removeItem(FLOATING_VIDEO_HIDDEN_KEY);
  window.dispatchEvent(new Event("last-watch-updated"));
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function readWatchLayout(): WatchLayout {
  if (typeof window === "undefined") return DEFAULT_WATCH_LAYOUT;
  try {
    const raw = window.localStorage.getItem(WATCH_LAYOUT_KEY);
    if (!raw) return DEFAULT_WATCH_LAYOUT;
    const value = JSON.parse(raw) as Partial<WatchLayout>;
    if (!Number.isFinite(value.leftWidth) || !Number.isFinite(value.videoHeight)) {
      return DEFAULT_WATCH_LAYOUT;
    }
    return {
      leftWidth: clamp(value.leftWidth ?? DEFAULT_WATCH_LAYOUT.leftWidth, 40, 70),
      videoHeight: clamp(value.videoHeight ?? DEFAULT_WATCH_LAYOUT.videoHeight, 35, 75),
    };
  } catch {
    return DEFAULT_WATCH_LAYOUT;
  }
}

function subtitleDomKey(subtitle: SubtitleLine): string {
  return subtitle.id != null ? `id:${subtitle.id}` : `time:${subtitle.start}:${subtitle.text}`;
}

function hasCompletedSubtitles(subtitles: SubtitleLine[]): boolean {
  return subtitles.length > 0 && subtitles.every((subtitle) => subtitle.processing_status === "processed");
}

function getVietnameseText(subtitle: SubtitleLine): string {
  const translation = subtitle.translation?.trim();
  const meanings = (subtitle.tokens ?? [])
    .map((token) => token.meaning?.trim())
    .filter((meaning): meaning is string => Boolean(meaning));

  if (translation && !translation.startsWith("[vi]")) {
    return translation;
  }

  if (meanings.length > 0) {
    return meanings.join(" / ");
  }

  return translation || "Đang dịch...";
}

export default function WatchPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-4xl px-4 py-10 text-slate-600">Đang tải trang xem...</main>}>
      <WatchContent />
    </Suspense>
  );
}
