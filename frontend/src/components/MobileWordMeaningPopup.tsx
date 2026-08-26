"use client";

import { Loader2, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { convertChineseText, type ChineseScript } from "@/lib/chinese-script";
import type { DictionaryEntry, SubtitleToken } from "@/types";

interface Props {
  entry: DictionaryEntry | null;
  error: string | null;
  loading: boolean;
  onClose: () => void;
  onSave: () => void;
  saveStatus: string | null;
  saving: boolean;
  script: ChineseScript;
  token: SubtitleToken;
}

export function MobileWordMeaningPopup({ entry, error, loading, onClose, onSave, saveStatus, saving, script, token }: Props) {
  const [portalReady, setPortalReady] = useState(false);
  const pinyin = entry?.pinyin ?? token.pinyin ?? "";
  const fallbackMeaning = entry?.meaning ?? token.meaning ?? "";
  const meanings = entry?.meanings?.length ? entry.meanings.map((item) => item.meaning) : fallbackMeaning ? [fallbackMeaning] : [];

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setPortalReady(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  if (!portalReady) return null;

  return createPortal(
    <div aria-label={`Nghĩa của ${token.text}`} aria-modal="true" className="fixed inset-0 z-[70] md:hidden" role="dialog">
      <button aria-label="Đóng popup nghĩa" className="absolute inset-0 bg-black/30" onClick={onClose} type="button" />
      <section className="absolute inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] max-h-[70dvh] overflow-y-auto rounded-2xl border border-cream-200 bg-cream-50 p-4 shadow-2xl">
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="break-words font-serif text-3xl font-bold leading-tight text-slate-800">
              {convertChineseText(token.text, script)}
            </h2>
            {pinyin ? <p className="mt-1 font-mono text-base font-semibold text-brand-700">{pinyin}</p> : null}
          </div>
          <button aria-label="Đóng" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-cream-200" onClick={onClose} type="button">
            <X size={19} />
          </button>
        </header>

        <div className="mt-3 rounded-xl bg-cream-100/70 px-3 py-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Nghĩa</p>
          {loading ? (
            <p className="mt-2 inline-flex items-center gap-2 text-sm text-slate-600">
              <Loader2 className="animate-spin text-brand-700" size={16} />
              Đang tra nghĩa...
            </p>
          ) : error ? (
            <p className="mt-2 text-sm leading-6 text-red-700">{error}</p>
          ) : meanings.length ? (
            <div className="mt-2 space-y-1.5">
              {meanings.map((meaning, index) => (
                <p className="text-base font-semibold leading-6 text-slate-800" key={`${meaning}-${index}`}>
                  {meanings.length > 1 ? `${index + 1}. ` : ""}{meaning}
                </p>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Chưa có nghĩa tiếng Việt.</p>
          )}
        </div>

        {saveStatus ? <p className="mt-3 rounded-lg bg-brand-100 px-3 py-2 text-sm font-medium text-brand-800">{saveStatus}</p> : null}
        <button
          className="mt-3 inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 text-sm font-semibold text-cream-50 hover:bg-brand-800 disabled:opacity-60"
          disabled={loading || saving}
          onClick={onSave}
          type="button"
        >
          {saving ? <Loader2 className="animate-spin" size={17} /> : <Save size={17} />}
          {saving ? "Đang lưu" : "Lưu từ"}
        </button>
      </section>
    </div>,
    document.body,
  );
}
