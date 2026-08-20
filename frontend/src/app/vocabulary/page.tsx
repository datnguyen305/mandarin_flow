"use client";

import Link from "next/link";
import { AlertCircle, ChevronDown, ExternalLink, Loader2, Plus, Trash2 } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { deleteVocabulary, listVocabulary, lookupWord } from "@/lib/api";
import { formatTimestamp } from "@/lib/subtitles";
import type { DictionaryEntry, SavedVocabulary } from "@/types";

export default function VocabularyPage() {
  const [items, setItems] = useState<SavedVocabulary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [detailsById, setDetailsById] = useState<Record<number, DictionaryEntry | undefined>>({});
  const [detailsLoadingById, setDetailsLoadingById] = useState<Record<number, boolean>>({});
  const [detailsErrorById, setDetailsErrorById] = useState<Record<number, string | undefined>>({});

  useEffect(() => {
    listVocabulary()
      .then(setItems)
      .catch((exc) => setError(exc instanceof Error ? exc.message : "Unable to load vocabulary."))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: number) {
    await deleteVocabulary(id);
    setItems((current) => current.filter((item) => item.id !== id));
  }

  async function toggleDetails(item: SavedVocabulary) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        next.add(item.id);
      }
      return next;
    });

    if (expandedIds.has(item.id) || detailsById[item.id] || detailsLoadingById[item.id]) return;

    setDetailsErrorById((current) => ({ ...current, [item.id]: undefined }));
    setDetailsLoadingById((current) => ({ ...current, [item.id]: true }));
    try {
      const details = await lookupWord(item.word, item.subtitle_sentence);
      setDetailsById((current) => ({ ...current, [item.id]: details }));
    } catch (exc) {
      setDetailsErrorById((current) => ({ ...current, [item.id]: exc instanceof Error ? exc.message : "Không thể tải chi tiết nghĩa." }));
    } finally {
      setDetailsLoadingById((current) => ({ ...current, [item.id]: false }));
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-brand-900">Sổ từ vựng</h1>
          <p className="mt-1 text-sm text-slate-500">{items.length} từ đã lưu cùng ngữ cảnh video</p>
        </div>
        <Link className="inline-flex items-center gap-2 rounded-md bg-brand-700 px-3 py-2 text-sm font-semibold text-cream-50 hover:bg-brand-800" href="/">
          <Plus size={16} />
          Thêm
        </Link>
      </div>
      {error ? <p className="text-red-600">{error}</p> : null}
      {loading ? (
        <div className="flex min-h-48 items-center justify-center gap-3 rounded-md border border-cream-200 bg-cream-50 text-sm text-slate-600">
          <Loader2 className="animate-spin text-brand-700" size={20} />
          Đang tải từ vựng...
        </div>
      ) : null}
      {!loading ? <div className="hidden overflow-hidden rounded-md border border-cream-200 bg-cream-50 shadow-sm md:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-cream-100 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Từ</th>
              <th className="px-4 py-3">Nghĩa</th>
              <th className="px-4 py-3">Ngữ cảnh gốc</th>
              <th className="px-4 py-3">Ôn tập</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const expanded = expandedIds.has(item.id);
              return (
                <Fragment key={item.id}>
                  <tr className="border-t border-cream-200 align-top">
                    <td className="px-4 py-4">
                      <div className="font-serif text-2xl font-bold text-ink">{item.word}</div>
                      <div className="mt-1 font-mono text-brand-700">{item.pinyin}</div>
                    </td>
                    <td className="px-4 py-4 text-slate-800">{item.meaning}</td>
                    <td className="px-4 py-4">
                      <Link className="font-medium text-ink hover:text-jade" href={`/watch?v=${item.youtube_video_id}&t=${Math.floor(item.timestamp)}`}>
                        {item.subtitle_sentence}
                      </Link>
                      <div className="mt-1 text-xs text-slate-500">{item.video_title}</div>
                    </td>
                    <td className="px-4 py-4">
                      <Link className="inline-flex items-center gap-2 rounded-md bg-brand-700 px-3 py-2 text-xs font-semibold text-cream-50 hover:bg-brand-800" href={`/watch?v=${item.youtube_video_id}&t=${Math.floor(item.timestamp)}`}>
                        <ExternalLink size={14} />
                        {formatTimestamp(item.timestamp)}
                      </Link>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          aria-label={expanded ? "Ẩn chi tiết nghĩa" : "Hiện chi tiết nghĩa"}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-2 text-xs font-semibold text-brand-800 hover:bg-cream-200"
                          onClick={() => toggleDetails(item)}
                          type="button"
                        >
                          Chi tiết
                          <ChevronDown className={`transition-transform ${expanded ? "rotate-180" : ""}`} size={15} />
                        </button>
                        <button aria-label="Delete word" className="rounded-md p-2 text-slate-500 hover:bg-cream-200" onClick={() => handleDelete(item.id)}>
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expanded ? (
                    <tr className="border-t border-cream-200 bg-cream-100/40">
                      <td className="px-4 py-4" colSpan={5}>
                        <VocabularyDetails
                          details={detailsById[item.id]}
                          error={detailsErrorById[item.id]}
                          fallbackMeaning={item.meaning}
                          loading={Boolean(detailsLoadingById[item.id])}
                        />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
            {items.length === 0 ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan={5}>
                  Chưa có từ vựng đã lưu.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div> : null}
      {!loading ? (
        <div className="space-y-3 md:hidden">
          {items.map((item) => (
            <article className="rounded-md border border-cream-200 bg-cream-50 p-4 shadow-sm" key={item.id}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-serif text-3xl font-bold text-ink">{item.word}</h2>
                  <p className="mt-1 font-mono text-brand-700">{item.pinyin}</p>
                </div>
                <button aria-label="Delete word" className="rounded-md p-2 text-slate-500 hover:bg-cream-200" onClick={() => handleDelete(item.id)}>
                  <Trash2 size={16} />
                </button>
              </div>
              <p className="mt-3 text-sm text-slate-800">{item.meaning}</p>
              <button
                className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-2 text-xs font-semibold text-brand-800 hover:bg-cream-200"
                onClick={() => toggleDetails(item)}
                type="button"
              >
                Chi tiết nghĩa
                <ChevronDown className={`transition-transform ${expandedIds.has(item.id) ? "rotate-180" : ""}`} size={15} />
              </button>
              {expandedIds.has(item.id) ? (
                <div className="mt-3">
                  <VocabularyDetails
                    details={detailsById[item.id]}
                    error={detailsErrorById[item.id]}
                    fallbackMeaning={item.meaning}
                    loading={Boolean(detailsLoadingById[item.id])}
                  />
                </div>
              ) : null}
              <Link className="mt-4 block text-sm font-medium text-ink hover:text-jade" href={`/watch?v=${item.youtube_video_id}&t=${Math.floor(item.timestamp)}`}>
                {item.subtitle_sentence}
              </Link>
              <p className="mt-1 text-xs text-slate-500">{item.video_title}</p>
              <Link className="mt-4 inline-flex items-center gap-2 rounded-md bg-brand-700 px-3 py-2 text-xs font-semibold text-cream-50" href={`/watch?v=${item.youtube_video_id}&t=${Math.floor(item.timestamp)}`}>
                <ExternalLink size={14} />
                Ôn tại {formatTimestamp(item.timestamp)}
              </Link>
            </article>
          ))}
          {items.length === 0 ? <p className="rounded-md border border-cream-200 bg-cream-50 px-4 py-8 text-center text-sm text-slate-500">Chưa có từ vựng đã lưu.</p> : null}
        </div>
      ) : null}
    </main>
  );
}

function VocabularyDetails({
  details,
  error,
  fallbackMeaning,
  loading,
}: {
  details?: DictionaryEntry;
  error?: string;
  fallbackMeaning?: string | null;
  loading: boolean;
}) {
  const meanings = details?.meanings?.length ? details.meanings : fallbackMeaning ? [{ meaning: fallbackMeaning }] : [];
  const context = details?.context;
  const collocations = details?.collocations ?? [];
  const examples = details?.examples ?? [];

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-cream-200 bg-cream-50 px-3 py-3 text-sm text-slate-600">
        <Loader2 className="animate-spin text-brand-700" size={16} />
        Đang tải chi tiết nghĩa...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
        <AlertCircle className="mt-0.5 shrink-0" size={16} />
        {error}
      </div>
    );
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <section className="rounded-md border border-cream-200 bg-cream-50 p-3">
        <p className="text-xs font-semibold uppercase text-slate-500">Nghĩa</p>
        <div className="mt-2 space-y-2">
          {meanings.map((item, index) => (
            <div key={`${item.meaning}-${index}`}>
              <p className="font-semibold text-ink">{meanings.length > 1 ? `${toCircledNumber(index + 1)} ` : ""}{item.meaning}</p>
              {item.definition ? <p className="mt-1 text-sm leading-6 text-slate-600">{item.definition}</p> : null}
            </div>
          ))}
        </div>
      </section>

      {context ? (
        <section className="rounded-md border border-cream-200 bg-cream-50 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Trong câu này</p>
          {context.phrase ? <p className="mt-2 font-serif text-xl font-semibold text-ink">{context.phrase}</p> : null}
          {context.phrase_pinyin ? <p className="mt-1 font-mono text-sm font-semibold text-brand-700">{context.phrase_pinyin}</p> : null}
          <p className="mt-2 text-sm font-semibold text-slate-800">{context.phrase_meaning ?? context.selected_meaning}</p>
          {context.explanation ? <p className="mt-2 text-sm leading-6 text-slate-600"><span className="font-semibold text-slate-700">Giải thích: </span>{context.explanation}</p> : null}
        </section>
      ) : null}

      {collocations.length > 0 ? (
        <section className="rounded-md border border-cream-200 bg-cream-50 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Cụm từ thường gặp</p>
          <div className="mt-2 space-y-2">
            {collocations.slice(0, 5).map((item) => (
              <div key={`${item.text}-${item.pinyin}`}>
                <p className="font-serif text-lg font-semibold text-ink">{item.text}</p>
                <p className="font-mono text-xs font-semibold text-brand-700">{item.pinyin}</p>
                <p className="text-sm text-slate-700">{item.meaning}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {examples.length > 0 ? (
        <section className="rounded-md border border-cream-200 bg-cream-50 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Ví dụ</p>
          <div className="mt-2 space-y-3">
            {examples.slice(0, 2).map((item) => (
              <div key={`${item.chinese}-${item.pinyin}`}>
                <p className="font-serif text-lg font-semibold leading-7 text-ink">{item.chinese}</p>
                <p className="mt-1 font-mono text-xs font-semibold text-brand-700">{item.pinyin}</p>
                <p className="mt-1 text-sm leading-6 text-slate-700">{item.vietnamese}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function toCircledNumber(value: number) {
  const numerals = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"];
  return numerals[value - 1] ?? `${value}.`;
}
