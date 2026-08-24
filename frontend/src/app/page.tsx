"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { BookOpen, CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock3, Eye, Mail, MessageSquareText, Play, Search, Send, Sparkles, Tags, UserRound } from "lucide-react";
import { MotionConfig, motion, stagger, useReducedMotion } from "motion/react";
import { Suspense, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { listVideoProgress, listVideos, listVocabulary } from "@/lib/api";
import { ALL_VIDEO_TAGS, filterVideos, formatVideoDuration, getVideoTags, paginateVideos, parseVideoPage, videoCatalogUrl } from "@/lib/videoCatalog";
import { getPreferredYouTubeThumbnail } from "@/lib/youtubeThumbnail";
import type { ImportedVideo, SavedVocabulary, VideoProgress } from "@/types";
import { ImportChatbot } from "@/components/ImportChatbot";

const FEEDBACK_EMAIL = process.env.NEXT_PUBLIC_FEEDBACK_EMAIL ?? "";

export default function HomePage() {
  return (
    <MotionConfig reducedMotion="user">
      <Suspense fallback={<HomePageLoading />}>
        <HomePageContent />
      </Suspense>
    </MotionConfig>
  );
}

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tagMenuRef = useRef<HTMLDetailsElement>(null);
  const shouldReduceMotion = useReducedMotion();
  const [videos, setVideos] = useState<ImportedVideo[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedWordCounts, setSavedWordCounts] = useState<Record<string, number>>({});
  const [videoProgress, setVideoProgress] = useState<Record<string, VideoProgress>>({});
  const [dailyStats, setDailyStats] = useState({ savedWords: 0, watchedVideos: 0 });
  const [feedbackName, setFeedbackName] = useState("");
  const [feedbackContact, setFeedbackContact] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);

  useEffect(() => {
    async function loadHomeData() {
      try {
        // The vocabulary request establishes the guest cookie before other guest-scoped calls run.
        const [videoItems, vocabularyItems] = await Promise.all([listVideos(100), listVocabulary()]);
        const progressItems = await listVideoProgress();
        setVideos(videoItems);
        setSavedWordCounts(countSavedWordsByVideo(vocabularyItems));
        setVideoProgress(Object.fromEntries(progressItems.map((item) => [item.youtube_video_id, item])));
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        setDailyStats({
          savedWords: vocabularyItems.filter((item) => new Date(item.created_at) >= today).length,
          watchedVideos: progressItems.filter((item) => new Date(item.last_watched_at) >= today && item.current_time > 0).length,
        });
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Không thể tải video.");
      } finally {
        setLoading(false);
      }
    }

    loadHomeData();
  }, []);

  const requestedTag = searchParams.get("tag")?.trim() || ALL_VIDEO_TAGS;
  const selectedTag = requestedTag.toLocaleLowerCase("vi") === ALL_VIDEO_TAGS.toLocaleLowerCase("vi") ? ALL_VIDEO_TAGS : requestedTag;
  const requestedPage = parseVideoPage(searchParams.get("page"));
  const availableTags = useMemo(() => getVideoTags(videos), [videos]);
  const tagOptions = useMemo(() => {
    const options = [ALL_VIDEO_TAGS, ...availableTags];
    if (!options.some((tag) => tag.toLocaleLowerCase("vi") === selectedTag.toLocaleLowerCase("vi"))) options.push(selectedTag);
    return options;
  }, [availableTags, selectedTag]);
  const desktopTagOptions = useMemo(() => {
    const visible = tagOptions.slice(0, 5);
    const selectedOption = tagOptions.find((tag) => tag.toLocaleLowerCase("vi") === selectedTag.toLocaleLowerCase("vi"));

    if (selectedOption && !visible.includes(selectedOption)) visible[visible.length - 1] = selectedOption;

    return {
      visible,
      overflow: tagOptions.filter((tag) => !visible.includes(tag)),
    };
  }, [selectedTag, tagOptions]);
  const filteredVideos = useMemo(() => filterVideos(videos, selectedTag, query), [query, selectedTag, videos]);
  const pagination = useMemo(() => paginateVideos(filteredVideos, requestedPage), [filteredVideos, requestedPage]);

  useEffect(() => {
    if (!loading && pagination.page !== requestedPage) {
      router.replace(videoCatalogUrl(selectedTag, pagination.page), { scroll: false });
    }
  }, [loading, pagination.page, requestedPage, router, selectedTag]);

  function selectTag(tag: string) {
    tagMenuRef.current?.removeAttribute("open");
    router.replace(videoCatalogUrl(tag, 1), { scroll: false });
  }

  function selectPage(page: number) {
    if (page < 1 || page > pagination.totalPages || page === pagination.page) return;
    router.replace(videoCatalogUrl(selectedTag, page), { scroll: false });
  }

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
      <section className="mx-auto max-w-7xl p-4">
        <div className="mb-8">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-100/80 px-4 py-1.5 text-sm font-semibold text-brand-800">
            <Sparkles size={16} className="text-brand-500" />
            Học qua ngữ cảnh video có sẵn
          </div>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <AnimatedBrandTitle />
              <p className="mt-4 text-base leading-7 text-slate-500">
                Chọn video và học tiếng Trung thông qua tương tác trực tiếp.
              </p>
            </div>
            <div className="w-full rounded-2xl border border-cream-200 bg-cream-50 px-4 py-3 shadow-sm lg:w-[calc((100%-2rem)/3)]">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-700">
                <CalendarDays size={15} />
                <span>Daily Learning Stats</span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <strong className="block text-xl leading-none text-slate-800">{dailyStats.savedWords}</strong>
                  <span className="mt-1 block text-xs text-slate-500">Từ đã lưu hôm nay</span>
                </div>
                <div>
                  <strong className="block text-xl leading-none text-slate-800">{dailyStats.watchedVideos}</strong>
                  <span className="mt-1 block text-xs text-slate-500">Video đã học hôm nay</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mb-5 flex scroll-mt-20 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-route-scroll-anchor>
          <div className="min-w-0 flex-1" aria-label="Lọc video theo chủ đề">
            <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700 lg:hidden">
              <Tags size={17} className="text-brand-700" />
              <span>Lọc theo chủ đề</span>
            </div>
            <div className="scrollbar-none flex w-full gap-2 overflow-x-auto pb-1 lg:hidden">
              {tagOptions.map((tag) => (
                <TagFilterButton key={tag} tag={tag} selectedTag={selectedTag} onSelect={selectTag} />
              ))}
            </div>
            <div className="hidden h-12 min-w-0 items-center gap-2 lg:flex">
              <div className="mr-1 flex shrink-0 items-center gap-1.5 text-sm font-semibold text-slate-700">
                <Tags size={16} className="text-brand-700" />
                <span>Lọc theo chủ đề</span>
              </div>
              {desktopTagOptions.visible.map((tag) => (
                <TagFilterButton key={tag} tag={tag} selectedTag={selectedTag} onSelect={selectTag} />
              ))}
              {desktopTagOptions.overflow.length > 0 ? (
                <details className="group relative shrink-0" ref={tagMenuRef}>
                  <summary
                    aria-label="Xem thêm chủ đề"
                    className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full border border-cream-300 bg-cream-50 text-slate-600 transition hover:border-brand-300 hover:text-brand-800 [&::-webkit-details-marker]:hidden"
                  >
                    <ChevronDown className="transition-transform group-open:rotate-180" size={16} />
                  </summary>
                  <div className="absolute left-0 top-11 z-20 min-w-40 rounded-lg border border-cream-200 bg-cream-50 p-1.5 shadow-lg">
                    {desktopTagOptions.overflow.map((tag) => {
                      const active = tag.toLocaleLowerCase("vi") === selectedTag.toLocaleLowerCase("vi");
                      return (
                        <button
                          aria-pressed={active}
                          className={`flex w-full items-center rounded-md px-3 py-2 text-left text-sm transition ${
                            active ? "bg-brand-700 font-semibold text-cream-50" : "text-slate-600 hover:bg-cream-100 hover:text-brand-800"
                          }`}
                          key={tag}
                          onClick={() => selectTag(tag)}
                          type="button"
                        >
                          {tag}
                        </button>
                      );
                    })}
                  </div>
                </details>
              ) : null}
            </div>
          </div>
          <label className="relative block w-full shrink-0 lg:w-[calc((100%-2rem)/3)]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
            <input
              className="h-12 w-full rounded-xl border border-cream-300 bg-cream-50 pl-10 pr-3 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="Tìm video để học"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                if (pagination.page !== 1) router.replace(videoCatalogUrl(selectedTag, 1), { scroll: false });
              }}
            />
          </label>
        </div>

        {error ? (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
            <p className="font-semibold">Không thể tải danh sách video.</p>
            <p className="mt-1">{error}</p>
          </div>
        ) : null}

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Đang tải video">
            {Array.from({ length: 6 }, (_, index) => (
              <div className="overflow-hidden rounded-2xl border border-cream-200 bg-cream-50" key={index}>
                <div className="aspect-video animate-pulse bg-cream-200" />
                <div className="space-y-3 p-4">
                  <div className="h-5 w-4/5 animate-pulse rounded bg-cream-200" />
                  <div className="h-10 animate-pulse rounded-xl bg-cream-100" />
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {!loading && !error && filteredVideos.length > 0 ? (
          <motion.div
            animate="visible"
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
            initial={shouldReduceMotion ? false : "hidden"}
            variants={{
              visible: { transition: { delayChildren: stagger(0.09) } },
            }}
          >
            {pagination.items.map((video) => {
              const progress = videoProgress[video.youtube_video_id];
              const watchHref = `/watch?v=${video.youtube_video_id}${progress?.current_time ? `&t=${Math.floor(progress.current_time)}` : ""}`;
              return (
              <motion.article
                className="overflow-hidden rounded-3xl border border-cream-200 bg-cream-50 shadow-sm transition hover:border-brand-200 hover:shadow-md"
                key={video.id}
                variants={{
                  hidden: { opacity: 0, y: 18 },
                  visible: { opacity: 1, y: 0, transition: { duration: 0.52, ease: [0.22, 1, 0.36, 1] } },
                }}
              >
                <Link href={watchHref} className="block">
                  <div className="relative aspect-video bg-[#172d59]">
                    {video.thumbnail_url ? (
                      <Image
                        alt={video.title}
                        className="object-contain"
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
                <div className="w-full p-4 sm:p-5">
                  <Link className="line-clamp-2 min-h-14 text-base font-bold leading-tight text-brand-950 hover:text-brand-700 sm:text-lg" href={watchHref}>
                    {video.title}
                  </Link>
                  <div className="mt-2 flex min-h-5 items-center justify-between gap-3 text-sm text-slate-500">
                    <p className="flex min-w-0 items-center gap-1.5">
                      <UserRound className="shrink-0 text-brand-700" size={15} strokeWidth={1.8} />
                      <span className="truncate">{video.channel_name || "Không rõ tác giả"}</span>
                    </p>
                    {video.view_count != null ? (
                      <span className="flex shrink-0 items-center gap-1.5" title={`${video.view_count.toLocaleString("vi-VN")} lượt xem`}>
                        <Eye className="text-brand-700" size={15} strokeWidth={1.8} />
                        {formatViewCount(video.view_count)}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-3 flex w-full flex-wrap items-center justify-center gap-x-5 gap-y-3 text-sm text-brand-950">
                    {formatVideoDuration(video.duration_seconds) ? (
                      <span className="inline-flex items-center gap-2">
                        <Clock3 className="text-brand-800" size={22} strokeWidth={1.8} />
                        <span>{formatVideoDuration(video.duration_seconds)}</span>
                      </span>
                    ) : null}
                    <span className="inline-flex items-center gap-2">
                      <Play className="text-brand-800" size={22} strokeWidth={1.8} />
                      <span>{progress?.current_time ? formatPlaybackTime(progress.current_time) : "Chưa học"}</span>
                    </span>
                    <span className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#edf3ef] px-3 py-2 font-semibold text-[#365b45]">
                      <BookOpen className="shrink-0" size={22} strokeWidth={1.8} />
                      <span>Đã lưu {savedWordCounts[video.youtube_video_id] ?? 0} từ</span>
                    </span>
                  </div>
                </div>
              </motion.article>
              );
            })}
          </motion.div>
        ) : null}

        {!loading && !error && filteredVideos.length === 0 ? (
          <div className="rounded-2xl border border-cream-200 bg-cream-50 px-4 py-12 text-center">
            <p className="font-medium text-slate-700">
              {videos.length === 0
                ? "Chưa có video nào sẵn sàng."
                : selectedTag !== ALL_VIDEO_TAGS
                  ? "Không có video phù hợp với chủ đề này."
                  : "Không tìm thấy video phù hợp."}
            </p>
          </div>
        ) : null}

        {!loading && !error && filteredVideos.length > 6 ? (
          <nav className="mt-6 flex items-center justify-center gap-3" aria-label="Phân trang video">
            <button
              aria-label="Trang trước"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-cream-300 bg-cream-50 text-brand-800 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!pagination.hasPrevious}
              onClick={() => selectPage(pagination.page - 1)}
              type="button"
            >
              <ChevronLeft size={19} />
            </button>
            <span className="min-w-20 text-center text-sm font-semibold text-slate-700">
              {pagination.page} / {pagination.totalPages}
            </span>
            <button
              aria-label="Trang sau"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-cream-300 bg-cream-50 text-brand-800 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!pagination.hasNext}
              onClick={() => selectPage(pagination.page + 1)}
              type="button"
            >
              <ChevronRight size={19} />
            </button>
          </nav>
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
      <ImportChatbot />
    </main>
  );
}

function AnimatedBrandTitle() {
  const title = "MandarinFlow";
  const shouldReduceMotion = useReducedMotion();

  if (shouldReduceMotion) {
    return <h1 className="text-4xl font-bold leading-tight tracking-normal text-slate-800 sm:text-5xl">{title}</h1>;
  }

  return (
    <h1 aria-label={title} className="text-4xl font-bold leading-tight tracking-normal text-slate-800 sm:text-5xl">
      <motion.span
        animate="visible"
        aria-hidden="true"
        className="inline-flex"
        initial="hidden"
        variants={{ visible: { transition: { delayChildren: stagger(0.075, { startDelay: 0.18 }) } } }}
      >
        {Array.from(title).map((character, index) => (
          <motion.span
            key={`${character}-${index}`}
            variants={{
              hidden: { opacity: 0, y: "0.12em" },
              visible: { opacity: 1, y: 0, transition: { duration: 0.16, ease: "easeOut" } },
            }}
          >
            {character}
          </motion.span>
        ))}
        <motion.span
          animate={{ opacity: [0, 1, 0, 1, 0] }}
          className="ml-[3px] h-[0.9em] w-0.5 self-center bg-brand-700"
          transition={{ delay: 0.18, duration: 1.9, ease: "linear", times: [0, 0.18, 0.4, 0.62, 1] }}
        />
      </motion.span>
    </h1>
  );
}

function HomePageLoading() {
  return <main className="min-h-[calc(100vh-57px)] bg-rice" />;
}

function TagFilterButton({
  tag,
  selectedTag,
  onSelect,
}: {
  tag: string;
  selectedTag: string;
  onSelect: (tag: string) => void;
}) {
  const active = tag.toLocaleLowerCase("vi") === selectedTag.toLocaleLowerCase("vi");

  return (
    <button
      aria-pressed={active}
      className={`h-9 shrink-0 rounded-full border px-3.5 text-sm font-semibold transition ${
        active
          ? "border-brand-700 bg-brand-700 text-cream-50 shadow-sm"
          : "border-cream-300 bg-cream-50 text-slate-600 hover:border-brand-300 hover:text-brand-800"
      }`}
      onClick={() => onSelect(tag)}
      type="button"
    >
      {tag}
    </button>
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

function formatViewCount(count: number): string {
  if (count >= 1_000_000_000) return `${formatCompactNumber(count / 1_000_000_000)} Tỷ lượt xem`;
  if (count >= 1_000_000) return `${formatCompactNumber(count / 1_000_000)} Tr lượt xem`;
  if (count >= 1_000) return `${formatCompactNumber(count / 1_000)} N lượt xem`;
  return `${count.toLocaleString("vi-VN")} lượt xem`;
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value);
}
