"use client";

import { AlertCircle, BookMarked, GripVertical, Loader2, Pause, Save, X } from "lucide-react";
import { type CSSProperties, type RefObject, useEffect, useState } from "react";
import { HanziStrokeWriter } from "@/components/HanziStrokeWriter";
import { convertChineseText, type ChineseScript } from "@/lib/chinese-script";
import type { DictionaryEntry, SubtitleLine, SubtitleToken } from "@/types";

interface Props {
  anchorRef: RefObject<HTMLElement | null>;
  token: SubtitleToken;
  entry: DictionaryEntry | null;
  loading: boolean;
  error: string | null;
  subtitle: SubtitleLine | null;
  onClose: () => void;
  onPause: () => void;
  onSave: () => void;
  saving: boolean;
  saveStatus: string | null;
  script: ChineseScript;
}

export function DictionaryPanel({ anchorRef, token, entry, loading, error, subtitle, onClose, onPause, onSave, saving, saveStatus, script }: Props) {
  const [panelWidth, setPanelWidth] = useState(448);
  const [verticalBounds, setVerticalBounds] = useState({ top: 57, bottom: 8 });
  const pinyin = entry?.pinyin ?? token.pinyin ?? "";
  const meaning = entry?.meaning ?? token.meaning ?? "";
  const meanings = entry?.meanings?.length ? entry.meanings : meaning ? [{ meaning }] : [];
  const collocations = entry?.collocations ?? [];
  const examples = entry?.examples ?? [];
  const sourceSentence = subtitle?.text ?? entry?.example_zh ?? "";
  const subtitleTranslation = cleanVietnameseExample(subtitle?.translation);
  const displayWord = convertChineseText(token.text, script);

  useEffect(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;

    function syncVerticalBounds() {
      const rect = anchor?.getBoundingClientRect();
      if (!rect) return;
      if (rect.width === 0 || rect.height === 0) {
        setVerticalBounds({ top: 0, bottom: 0 });
        return;
      }
      setVerticalBounds({
        top: Math.round(rect.top),
        bottom: Math.round(Math.max(0, window.innerHeight - rect.bottom)),
      });
    }

    syncVerticalBounds();
    const observer = new ResizeObserver(syncVerticalBounds);
    observer.observe(anchor);
    window.addEventListener("resize", syncVerticalBounds);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", syncVerticalBounds);
    };
  }, [anchorRef]);

  function resizePanel(nextWidth: number) {
    const viewportLimit = typeof window === "undefined" ? 720 : window.innerWidth * 0.7;
    setPanelWidth(Math.round(Math.min(720, viewportLimit, Math.max(320, nextWidth))));
  }

  function beginResize(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const startX = event.clientX;
    const startWidth = panelWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    function handlePointerMove(pointerEvent: PointerEvent) {
      resizePanel(startWidth + startX - pointerEvent.clientX);
    }

    function finishResize() {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("pointerup", finishResize);
    }

    document.addEventListener("pointermove", handlePointerMove);
    document.addEventListener("pointerup", finishResize, { once: true });
  }

  return (
    <aside
      className="fixed inset-y-0 right-0 z-30 flex min-h-0 w-full flex-col overflow-hidden border-l border-cream-200 bg-cream-50 shadow-2xl sm:bottom-auto sm:top-[var(--dictionary-top)] sm:h-[var(--dictionary-height)] sm:w-[var(--dictionary-width)] sm:max-w-[70vw] sm:rounded-l-xl sm:border-y"
      style={{
        "--dictionary-width": `${panelWidth}px`,
        "--dictionary-top": `${verticalBounds.top}px`,
        "--dictionary-bottom": `${verticalBounds.bottom}px`,
        "--dictionary-height": `calc(100dvh - ${verticalBounds.top}px - ${verticalBounds.bottom}px)`,
      } as CSSProperties}
    >
      <div
        aria-label="Điều chỉnh chiều rộng từ điển nhanh"
        aria-orientation="vertical"
        aria-valuemax={720}
        aria-valuemin={320}
        aria-valuenow={panelWidth}
        className="group absolute inset-y-0 left-0 z-10 hidden w-3 -translate-x-1/2 cursor-col-resize touch-none items-center justify-center sm:flex"
        onDoubleClick={() => setPanelWidth(448)}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") resizePanel(panelWidth + 24);
          if (event.key === "ArrowRight") resizePanel(panelWidth - 24);
        }}
        onPointerDown={beginResize}
        role="separator"
        tabIndex={0}
        title="Kéo để thay đổi chiều rộng; nhấp đúp để đặt lại"
      >
        <span className="flex h-12 w-5 items-center justify-center rounded-full border border-cream-300 bg-cream-50 text-slate-400 shadow-sm transition group-hover:border-brand-300 group-hover:text-brand-700 group-focus:border-brand-300 group-focus:text-brand-700">
          <GripVertical size={14} />
        </span>
      </div>
      <div className="border-b border-cream-200 bg-cream-100/70 px-5 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-2">
            <BookMarked className="shrink-0 text-brand-700" size={18} />
            <p className="truncate text-base font-semibold text-brand-900">Từ điển nhanh</p>
          </div>
          <button aria-label="Đóng từ điển" className="rounded-lg p-2 text-slate-500 hover:bg-cream-200" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        <div className="mb-5 grid gap-3 rounded-lg border border-cream-200 bg-white p-4 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="break-words font-serif text-5xl font-bold leading-tight text-slate-800">{displayWord}</h2>
              {pinyin ? <p className="mt-2 break-words font-mono text-xl font-semibold text-brand-700">{pinyin}</p> : null}
            </div>
            {entry?.part_of_speech ? <span className="shrink-0 rounded-md bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-800">{entry.part_of_speech}</span> : null}
          </div>
          <div className="hidden sm:block">
            <HanziStrokeWriter key={displayWord} text={displayWord} compact />
          </div>
        </div>

        {loading ? (
          <div className="mb-5 flex items-center gap-2 rounded-lg border border-cream-200 bg-cream-100/60 px-3 py-2 text-sm text-slate-600">
            <Loader2 className="animate-spin text-brand-700" size={16} />
            Đang tra nghĩa...
          </div>
        ) : null}

        {error ? (
          <div className="mb-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertCircle className="mt-0.5 shrink-0" size={16} />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="space-y-3">
          <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">Nghĩa</p>
            {meanings.length > 0 ? (
              <div className="mt-3 space-y-3">
                {meanings.map((item, index) => (
                  <div className="space-y-1" key={`${item.meaning}-${index}`}>
                    <p className="break-words text-lg font-semibold leading-7 text-ink">
                      {meanings.length > 1 ? `${toCircledNumber(index + 1)} ` : ""}
                      {item.meaning}
                    </p>
                    {item.definition ? <p className="break-words text-sm leading-6 text-slate-600">{item.definition}</p> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-1 break-words text-xl font-semibold leading-7 text-ink">Chưa có nghĩa tiếng Việt.</p>
            )}
          </section>

          {collocations.length > 0 ? (
            <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Cụm từ thường gặp</p>
              <div className="mt-3 space-y-2">
                {collocations.map((item) => (
                  <div className="rounded-lg bg-cream-50 px-3 py-2" key={`${item.text}-${item.pinyin}`}>
                    <p className="break-words font-serif text-lg font-semibold leading-7 text-ink">{convertChineseText(item.text, script)}</p>
                    <p className="mt-1 break-words font-mono text-sm font-semibold text-brand-700">{item.pinyin}</p>
                    <p className="mt-1 break-words text-sm leading-6 text-slate-700">{item.meaning}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {examples.length > 0 ? (
            <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Ví dụ</p>
              <div className="mt-3 space-y-3">
                {examples.map((item) => (
                  <div className="rounded-lg bg-cream-50 px-3 py-2" key={`${item.chinese}-${item.pinyin}`}>
                    <p className="break-words font-serif text-lg font-semibold leading-8 text-ink">{convertChineseText(item.chinese, script)}</p>
                    <p className="mt-1 break-words font-mono text-sm font-semibold text-brand-700">{item.pinyin}</p>
                    <p className="mt-2 break-words text-sm leading-6 text-slate-700">{item.vietnamese}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3 sm:hidden">
            <p className="text-xs font-semibold uppercase text-slate-500">Cách viết</p>
            <div className="mt-3">
              <HanziStrokeWriter key={`inline-${displayWord}`} text={displayWord} compact />
            </div>
          </section>

          <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">Câu gốc</p>
            <p className="mt-1 break-words font-serif text-lg font-semibold leading-8 text-ink">
              {sourceSentence ? convertChineseText(sourceSentence, script) : "Không có câu gốc."}
            </p>
            {subtitleTranslation ? <p className="mt-2 break-words text-base leading-7 text-slate-700">{subtitleTranslation}</p> : null}
          </section>
        </div>
      </div>

      <div className="border-t border-cream-200 bg-cream-100/70 p-4">
        {saveStatus ? <p className="mb-3 rounded-lg bg-brand-100 px-3 py-2 text-sm text-brand-800">{saveStatus}</p> : null}
        <div className="grid grid-cols-2 gap-3">
          <button className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-sm hover:bg-cream-200" onClick={onPause}>
            <Pause size={16} />
            Tạm dừng
          </button>
          <button
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-brand-700 px-3 py-2 text-sm font-semibold text-cream-50 hover:bg-brand-800 disabled:opacity-60"
            disabled={saving || loading}
            onClick={onSave}
          >
            {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
            {saving ? "Đang lưu" : "Lưu từ"}
          </button>
        </div>
      </div>
    </aside>
  );
}

function cleanVietnameseExample(value?: string | null): string {
  const text = value?.trim();
  if (!text || text.startsWith("[vi]")) {
    return "";
  }
  return text;
}

function toCircledNumber(value: number) {
  const numerals = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"];
  return numerals[value - 1] ?? `${value}.`;
}
