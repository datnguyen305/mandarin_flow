"use client";

import { AlertCircle, BookOpenCheck, Loader2, Search } from "lucide-react";
import { type FormEvent, useState } from "react";
import { HanziStrokeWriter } from "@/components/HanziStrokeWriter";
import { lookupWord } from "@/lib/api";
import type { DictionaryEntry } from "@/types";

export default function DictionaryPage() {
  const [query, setQuery] = useState("");
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const word = query.trim();
    if (!word || loading) return;

    setLoading(true);
    setError(null);
    try {
      setEntry(await lookupWord(word));
    } catch (lookupError) {
      setEntry(null);
      setError(lookupError instanceof Error ? lookupError.message : "Không thể tra từ lúc này.");
    } finally {
      setLoading(false);
    }
  }

  const meanings = entry?.meanings?.length
    ? entry.meanings
    : entry?.meaning
      ? [{ meaning: entry.meaning }]
      : [];

  return (
    <main className="min-h-[calc(100vh-57px)] bg-rice">
      <section className="mx-auto max-w-7xl px-3 py-5 sm:p-4 sm:py-8">
        <div className="grid gap-5 lg:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.28fr)] lg:items-start">
          <section className="lg:sticky lg:top-20">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-800">
                <BookOpenCheck aria-hidden="true" size={21} />
              </span>
              <div>
                <h1 className="text-2xl font-bold text-slate-800 sm:text-3xl">Tra từ nhanh</h1>
                <p className="mt-1 text-sm text-slate-500">Nghĩa tiếng Việt, pinyin và cách viết.</p>
              </div>
            </div>

            <form className="mt-5 rounded-2xl border border-cream-200 bg-cream-50 p-3 shadow-sm" onSubmit={handleLookup}>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="dictionary-word">
                Từ tiếng Trung
              </label>
              <div className="mt-2 flex gap-2">
                <div className="relative min-w-0 flex-1">
                  <Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
                  <input
                    autoComplete="off"
                    autoFocus
                    className="h-11 w-full rounded-xl border border-cream-300 bg-white pl-10 pr-3 text-base text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                    id="dictionary-word"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Ví dụ: 学习"
                    value={query}
                  />
                </div>
                <button
                  className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 text-sm font-semibold text-cream-50 transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!query.trim() || loading}
                  type="submit"
                >
                  {loading ? <Loader2 aria-hidden="true" className="animate-spin" size={17} /> : <Search aria-hidden="true" size={17} />}
                  Tra từ
                </button>
              </div>
            </form>

            {error ? (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                <span>{error}</span>
              </div>
            ) : null}
          </section>

          <section className="min-h-[360px] rounded-2xl border border-cream-200 bg-cream-50 p-4 shadow-sm sm:p-5">
            {!entry && !loading ? (
              <div className="flex min-h-[320px] flex-col items-center justify-center text-center text-slate-500">
                <Search aria-hidden="true" className="text-brand-300" size={30} />
                <p className="mt-3 text-sm">Nhập một từ tiếng Trung để bắt đầu tra cứu.</p>
              </div>
            ) : null}

            {loading ? (
              <div className="flex min-h-[320px] items-center justify-center gap-2 text-sm text-slate-500">
                <Loader2 aria-hidden="true" className="animate-spin text-brand-700" size={20} />
                Đang tra nghĩa...
              </div>
            ) : null}

            {entry && !loading ? (
              <div className="space-y-4">
                <div className="grid gap-4 rounded-xl border border-cream-200 bg-white p-4 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className="break-words font-serif text-5xl font-bold leading-tight text-slate-800">{entry.word}</h2>
                        {entry.pinyin ? <p className="mt-2 font-mono text-xl font-semibold text-brand-700">{entry.pinyin}</p> : null}
                      </div>
                      {entry.part_of_speech ? (
                        <span className="rounded-md bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-800">{entry.part_of_speech}</span>
                      ) : null}
                    </div>
                  </div>
                  <HanziStrokeWriter key={entry.word} text={entry.word} compact />
                </div>

                <section className="rounded-xl border border-cream-200 bg-cream-100/50 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Nghĩa</h3>
                  {meanings.length ? (
                    <div className="mt-3 space-y-3">
                      {meanings.map((item, index) => (
                        <div key={`${item.meaning}-${index}`}>
                          <p className="text-lg font-semibold leading-7 text-slate-800">
                            {meanings.length > 1 ? `${index + 1}. ` : ""}{item.meaning}
                          </p>
                          {item.definition ? <p className="mt-1 text-sm leading-6 text-slate-600">{item.definition}</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">Chưa có nghĩa tiếng Việt.</p>
                  )}
                </section>

                {entry.collocations?.length ? (
                  <section className="rounded-xl border border-cream-200 bg-cream-100/50 p-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cụm từ thường gặp</h3>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {entry.collocations.map((item) => (
                        <div className="rounded-lg bg-white px-3 py-2.5" key={`${item.text}-${item.pinyin}`}>
                          <p className="font-serif text-lg font-semibold text-slate-800">{item.text}</p>
                          <p className="mt-1 font-mono text-sm font-semibold text-brand-700">{item.pinyin}</p>
                          <p className="mt-1 text-sm text-slate-600">{item.meaning}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}

                {entry.examples?.length ? (
                  <section className="rounded-xl border border-cream-200 bg-cream-100/50 p-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Ví dụ</h3>
                    <div className="mt-3 space-y-2">
                      {entry.examples.map((item) => (
                        <div className="rounded-lg bg-white px-3 py-2.5" key={`${item.chinese}-${item.pinyin}`}>
                          <p className="font-serif text-lg font-semibold leading-7 text-slate-800">{item.chinese}</p>
                          <p className="mt-1 font-mono text-sm font-semibold text-brand-700">{item.pinyin}</p>
                          <p className="mt-1 text-sm leading-6 text-slate-600">{item.vietnamese}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>
      </section>
    </main>
  );
}
