"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BookOpen, Clock, Loader2, Search, RotateCcw, Languages } from "lucide-react";
import { DictionaryPanel } from "@/components/DictionaryPanel";
import { YouTubePlayer, type YouTubePlayerHandle } from "@/components/YouTubePlayer";
import { API_BASE_URL, getRawSubtitles, lookupWord, saveVocabulary, updatePlaybackPosition } from "@/lib/api";
import { findActiveSubtitleIndex, formatTimestamp, mergeSubtitleBatch } from "@/lib/subtitles";
import { convertChineseText, type ChineseScript } from "@/lib/chinese-script";
import type { DictionaryEntry, SubtitleBatch, SubtitleLine, SubtitleToken } from "@/types";

const LAST_WATCH_HREF_KEY = "fluentmandarin:last-watch-href";
const FLOATING_VIDEO_HIDDEN_KEY = "fluentmandarin:floating-video-hidden";
const SUBTITLE_SCRIPT_KEY = "fluentmandarin:subtitle-script";

function WatchContent() {
  const searchParams = useSearchParams();
  const videoId = searchParams.get("v") ?? "";
  const startTime = Number(searchParams.get("t") ?? 0);
  const playerRef = useRef<YouTubePlayerHandle | null>(null);
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
  const lastPlaybackPostRef = useRef({ time: -1, sentAt: 0 });
  const transcriptItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  useEffect(() => {
    const savedScript = window.localStorage.getItem(SUBTITLE_SCRIPT_KEY);
    if (savedScript !== "simplified" && savedScript !== "traditional") return;
    const timer = window.setTimeout(() => setSubtitleScript(savedScript), 0);
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
    transcriptItemRefs.current.get(subtitleDomKey(activeSubtitle))?.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
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
      const entry = await lookupWord(token.text, subtitle.text);
      setDictionaryEntry(entry);
    } catch (exc) {
      setDictionaryError(exc instanceof Error ? exc.message : "Không thể tra từ này.");
    } finally {
      setDictionaryLoading(false);
    }
  }

  async function handleSave() {
    const sourceSubtitle = selectedSubtitle ?? activeSubtitle;
    if (!selectedToken || !sourceSubtitle?.id) return;
    setSaving(true);
    try {
      await saveVocabulary({
        word: selectedToken.text,
        pinyin: dictionaryEntry?.pinyin ?? selectedToken.pinyin,
        meaning: dictionaryEntry?.meaning ?? selectedToken.meaning,
        youtube_video_id: videoId,
        subtitle_id: sourceSubtitle.id,
        timestamp: sourceSubtitle.start
      });
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
    <main className="mx-auto grid h-[calc(100vh-49px)] max-h-[calc(100vh-49px)] max-w-[1600px] grid-cols-1 gap-3 overflow-hidden px-3 py-2 lg:grid-cols-[minmax(0,1.05fr)_minmax(380px,0.95fr)]">
      <section className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden">
        <div className="w-full overflow-hidden rounded-xl border border-cream-200 bg-cream-50 shadow-lg">
          <div className="aspect-video">
            <YouTubePlayer ref={playerRef} videoId={videoId} startTime={startTime} />
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
              <Link className="inline-flex h-7 items-center gap-1 rounded-md bg-brand-700 px-2 text-[11px] font-semibold text-cream-50 hover:bg-brand-800" href="/vocabulary">
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
      </section>

      <section className="min-h-0 overflow-hidden">
        <aside className="flex h-full min-h-0 max-h-full flex-col overflow-hidden rounded-xl border border-cream-200 bg-cream-50 shadow-sm">
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
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
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
      {selectedToken ? (
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
        />
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
