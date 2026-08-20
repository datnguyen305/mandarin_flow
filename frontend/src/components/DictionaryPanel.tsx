"use client";

import { AlertCircle, BookMarked, Loader2, Pause, Save, X } from "lucide-react";
import { HanziStrokeWriter } from "@/components/HanziStrokeWriter";
import type { DictionaryEntry, SubtitleLine, SubtitleToken } from "@/types";

interface Props {
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
}

export function DictionaryPanel({ token, entry, loading, error, subtitle, onClose, onPause, onSave, saving, saveStatus }: Props) {
  const pinyin = entry?.pinyin ?? token.pinyin ?? "";
  const meaning = entry?.meaning ?? token.meaning ?? "";
  const meanings = entry?.meanings?.length ? entry.meanings : meaning ? [{ meaning }] : [];
  const context = entry?.context;
  const contextualMeaning = context?.phrase_meaning ?? context?.selected_meaning ?? entry?.contextual_meaning;
  const collocations = entry?.collocations ?? [];
  const examples = entry?.examples ?? [];
  const sourceSentence = subtitle?.text ?? entry?.example_zh ?? "";
  const subtitleTranslation = cleanVietnameseExample(subtitle?.translation);

  return (
    <aside className="fixed inset-y-0 right-0 z-30 flex w-full max-w-md flex-col border-l border-cream-200 bg-cream-50 shadow-2xl sm:top-[49px]">
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
              <h2 className="break-words font-serif text-5xl font-bold leading-tight text-slate-800">{token.text}</h2>
              {pinyin ? <p className="mt-2 break-words font-mono text-xl font-semibold text-brand-700">{pinyin}</p> : null}
            </div>
            {entry?.part_of_speech ? <span className="shrink-0 rounded-md bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-800">{entry.part_of_speech}</span> : null}
          </div>
          <div className="hidden sm:block">
            <HanziStrokeWriter key={token.text} text={token.text} compact />
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

          {context || contextualMeaning || entry?.enrichment_error ? (
            <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Trong câu này</p>
              {context?.phrase ? (
                <div className="mt-3 rounded-lg bg-cream-50 px-3 py-2">
                  <p className="break-words font-serif text-xl font-semibold leading-8 text-ink">{context.phrase}</p>
                  {context.phrase_pinyin ? <p className="mt-1 break-words font-mono text-sm font-semibold text-brand-700">{context.phrase_pinyin}</p> : null}
                  {context.phrase_meaning ? <p className="mt-2 break-words text-base font-semibold leading-7 text-slate-800">{context.phrase_meaning}</p> : null}
                </div>
              ) : contextualMeaning ? (
                <p className="mt-2 break-words text-base font-semibold leading-7 text-slate-800">{contextualMeaning}</p>
              ) : null}
              {context?.explanation ? (
                <p className="mt-3 break-words text-sm leading-6 text-slate-600">
                  <span className="font-semibold text-slate-700">Giải thích: </span>
                  {context.explanation}
                </p>
              ) : null}
              {entry?.enrichment_error ? <p className="mt-3 text-sm leading-6 text-amber-700">{entry.enrichment_error}</p> : null}
            </section>
          ) : null}

          {collocations.length > 0 ? (
            <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Cụm từ thường gặp</p>
              <div className="mt-3 space-y-2">
                {collocations.map((item) => (
                  <div className="rounded-lg bg-cream-50 px-3 py-2" key={`${item.text}-${item.pinyin}`}>
                    <p className="break-words font-serif text-lg font-semibold leading-7 text-ink">{item.text}</p>
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
                    <p className="break-words font-serif text-lg font-semibold leading-8 text-ink">{item.chinese}</p>
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
              <HanziStrokeWriter key={`inline-${token.text}`} text={token.text} compact />
            </div>
          </section>

          <section className="rounded-lg border border-cream-200 bg-cream-100/50 p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">Câu gốc</p>
            <p className="mt-1 break-words font-serif text-lg font-semibold leading-8 text-ink">{sourceSentence || "Không có câu gốc."}</p>
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
