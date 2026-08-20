"use client";

import Image from "next/image";
import Link from "next/link";
import { BookOpen, Loader2, Mail, MessageSquareText, Play, Search, Send, Sparkles } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { listVideoProgress, listVideos, listVocabulary } from "@/lib/api";
import type { ImportedVideo, SavedVocabulary, VideoProgress } from "@/types";

const FEEDBACK_EMAIL = process.env.NEXT_PUBLIC_FEEDBACK_EMAIL ?? "";

function formatImportedDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export default function HomePage() {
  const [videos, setVideos] = useState<ImportedVideo[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedWordCounts, setSavedWordCounts] = useState<Record<string, number>>({});
  const [videoProgress, setVideoProgress] = useState<Record<string, VideoProgress>>({});
  const [feedbackName, setFeedbackName] = useState("");
  const [feedbackContact, setFeedbackContact] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);

  useEffect(() => {
    async function loadHomeData() {
      try {
        // The vocabulary request establishes the guest cookie before other guest-scoped calls run.
        const [videoItems, vocabularyItems] = await Promise.all([listVideos(), listVocabulary()]);
        const progressItems = await listVideoProgress();
        setVideos(videoItems);
        setSavedWordCounts(countSavedWordsByVideo(vocabularyItems));
        setVideoProgress(Object.fromEntries(progressItems.map((item) => [item.youtube_video_id, item])));
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Không thể tải video.");
      } finally {
        setLoading(false);
      }
    }

    loadHomeData();
  }, []);

  const filteredVideos = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return videos;
    return videos.filter((video) => video.title.toLowerCase().includes(normalized) || video.youtube_video_id.toLowerCase().includes(normalized));
  }, [query, videos]);

  function handleFeedbackSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!FEEDBACK_EMAIL) {
      setFeedbackStatus("Chưa cấu hình email nhận phản hồi. Dev cần đặt NEXT_PUBLIC_FEEDBACK_EMAIL.");
      return;
    }
    if (!feedbackMessage.trim()) {
      setFeedbackStatus("Vui lòng nhập nội dung phản hồi trước khi gửi.");
      return;
    }

    const subject = encodeURIComponent("[MandarinFlow] Phản hồi từ người dùng");
    const body = encodeURIComponent(
      [
        `Tên: ${feedbackName.trim() || "Không cung cấp"}`,
        `Liên hệ: ${feedbackContact.trim() || "Không cung cấp"}`,
        "",
        "Nội dung phản hồi:",
        feedbackMessage.trim(),
      ].join("\n")
    );
    window.location.href = `mailto:${FEEDBACK_EMAIL}?subject=${subject}&body=${body}`;
    setFeedbackStatus("Đã mở ứng dụng email để gửi phản hồi.");
  }

  return (
    <main className="min-h-[calc(100vh-57px)] bg-rice">
      <section className="mx-auto max-w-7xl px-4 py-8 sm:py-10">
        <div className="mb-8">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-100/80 px-4 py-1.5 text-sm font-semibold text-brand-800">
            <Sparkles size={16} className="text-brand-500" />
            Học qua ngữ cảnh video có sẵn
          </div>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <h1 className="text-4xl font-bold leading-tight tracking-normal text-slate-800 sm:text-5xl">MandarinFlow</h1>
              <p className="mt-4 text-base leading-7 text-slate-500">
                Chọn video đã được chuẩn bị phụ đề, bấm vào từng từ tiếng Trung để xem pinyin, nghĩa theo ngữ cảnh và lưu vào sổ từ vựng.
              </p>
            </div>
            <label className="relative block w-full lg:max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
              <input
                className="h-12 w-full rounded-xl border border-cream-300 bg-cream-50 pl-10 pr-3 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                placeholder="Tìm video để học"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          </div>
        </div>

        {error ? <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p> : null}

        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 rounded-2xl border border-cream-200 bg-cream-50 text-sm text-slate-600">
            <Loader2 className="animate-spin text-brand-700" size={20} />
            Đang tải video...
          </div>
        ) : null}

        {!loading && filteredVideos.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredVideos.map((video) => {
              const progress = videoProgress[video.youtube_video_id];
              const watchHref = `/watch?v=${video.youtube_video_id}${progress?.current_time ? `&t=${Math.floor(progress.current_time)}` : ""}`;
              return (
              <article className="overflow-hidden rounded-2xl border border-cream-200 bg-cream-50 shadow-sm transition hover:border-brand-200 hover:shadow-md" key={video.id}>
                <Link href={watchHref} className="block">
                  <div className="relative aspect-video bg-slate-900">
                    {video.thumbnail_url ? (
                      <Image alt={video.title} className="object-cover" fill sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw" src={video.thumbnail_url} />
                    ) : (
                      <div className="flex h-full items-center justify-center font-serif text-5xl font-bold text-cream-50">汉</div>
                    )}
                    <span className="absolute bottom-3 right-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-cream-50/90 text-brand-800 shadow-sm">
                      <Play size={17} />
                    </span>
                  </div>
                </Link>
                <div className="p-4">
                  <Link className="line-clamp-2 min-h-11 font-semibold leading-snug text-slate-800 hover:text-brand-700" href={watchHref}>
                    {video.title}
                  </Link>
                  <div className="mt-3 flex items-center gap-2 rounded-xl bg-cream-100 px-3 py-2 text-sm text-slate-700">
                    <BookOpen className="shrink-0 text-brand-700" size={16} />
                    <span>
                      Đã lưu <strong className="font-semibold text-brand-900">{savedWordCounts[video.youtube_video_id] ?? 0}</strong> từ
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
                    <span>{progress?.current_time ? `Xem tiếp từ ${formatPlaybackTime(progress.current_time)}` : formatImportedDate(video.created_at)}</span>
                    <span className="rounded-full bg-brand-100 px-2 py-1 font-medium text-brand-800">{video.language}</span>
                  </div>
                </div>
              </article>
              );
            })}
          </div>
        ) : null}

        {!loading && filteredVideos.length === 0 ? (
          <div className="rounded-2xl border border-cream-200 bg-cream-50 px-4 py-12 text-center">
            <p className="font-medium text-slate-700">{videos.length === 0 ? "Chưa có video nào sẵn sàng." : "Không tìm thấy video phù hợp."}</p>
          </div>
        ) : null}

        <section className="mt-10 grid gap-6 rounded-2xl border border-cream-200 bg-cream-50 p-5 shadow-sm lg:grid-cols-[0.8fr_1.2fr] lg:p-6">
          <div>
            <div className="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-brand-100 text-brand-800">
              <MessageSquareText size={22} />
            </div>
            <h2 className="text-2xl font-bold tracking-normal text-slate-800">Gửi phản hồi</h2>
            <p className="mt-3 text-base leading-7 text-slate-500">
              Bạn gặp lỗi, muốn đề xuất video mới hoặc góp ý cách học? Gửi phản hồi để MandarinFlow cải thiện trải nghiệm học.
            </p>
            {FEEDBACK_EMAIL ? (
              <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-cream-100 px-3 py-1.5 text-sm font-medium text-slate-600">
                <Mail size={15} className="text-brand-700" />
                Gửi đến email của dự án
              </p>
            ) : null}
          </div>

          <form className="grid gap-3" onSubmit={handleFeedbackSubmit}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-sm font-semibold text-slate-700">
                Tên của bạn
                <input
                  className="h-12 rounded-xl border border-cream-300 bg-cream-100/60 px-3 text-sm font-normal text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                  placeholder="Ví dụ: Đạt"
                  value={feedbackName}
                  onChange={(event) => setFeedbackName(event.target.value)}
                />
              </label>
              <label className="grid gap-1.5 text-sm font-semibold text-slate-700">
                Email hoặc cách liên hệ
                <input
                  className="h-12 rounded-xl border border-cream-300 bg-cream-100/60 px-3 text-sm font-normal text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                  placeholder="email, Zalo, Telegram..."
                  value={feedbackContact}
                  onChange={(event) => setFeedbackContact(event.target.value)}
                />
              </label>
            </div>
            <label className="grid gap-1.5 text-sm font-semibold text-slate-700">
              Nội dung phản hồi
              <textarea
                className="min-h-32 resize-y rounded-xl border border-cream-300 bg-cream-100/60 px-3 py-3 text-sm font-normal leading-6 text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                placeholder="Mô tả lỗi, góp ý giao diện hoặc video bạn muốn học..."
                value={feedbackMessage}
                onChange={(event) => setFeedbackMessage(event.target.value)}
              />
            </label>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="min-h-5 text-sm text-slate-500">{feedbackStatus}</p>
              <button className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand-700 px-5 text-sm font-semibold text-cream-50 shadow-sm transition hover:bg-brand-800" type="submit">
                <Send size={17} />
                Gửi phản hồi
              </button>
            </div>
          </form>
        </section>
      </section>

      <footer className="border-t border-cream-200/70 py-4 text-center text-xs text-slate-400">
        MandarinFlow © 2026 - Công cụ học tiếng Trung qua video thông minh
      </footer>
    </main>
  );
}

function countSavedWordsByVideo(items: SavedVocabulary[]): Record<string, number> {
  return items.reduce<Record<string, number>>((counts, item) => {
    counts[item.youtube_video_id] = (counts[item.youtube_video_id] ?? 0) + 1;
    return counts;
  }, {});
}

function formatPlaybackTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}
