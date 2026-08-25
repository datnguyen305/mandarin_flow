"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Bookmark, BookOpen, CalendarDays, ChartNoAxesColumnIncreasing, ChevronDown, ChevronLeft, ChevronRight, Clock3, Eye, Flame, Mail, MessageSquareText, PartyPopper, Search, Send, Sparkles, Tags, UserRound, type LucideIcon } from "lucide-react";
import { MotionConfig, motion, stagger, useReducedMotion } from "motion/react";
import { Suspense, type FormEvent, type MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { listVideoProgress, listVideos, listVocabulary } from "@/lib/api";
import { ALL_VIDEO_TAGS, filterVideos, formatVideoDuration, getVideoTags, paginateVideos, parseVideoPage, videoCatalogUrl } from "@/lib/videoCatalog";
import { getPreferredYouTubeThumbnail } from "@/lib/youtubeThumbnail";
import type { ImportedVideo, SavedVocabulary, VideoProgress } from "@/types";
import { ImportChatbot } from "@/components/ImportChatbot";
import {
  LEARNING_PROGRESS_EVENT,
  countWordsSavedToday,
  nextWordMilestone,
  notifyLearningProgress,
  readLatestLearningProgress,
  type LearningProgressDetail,
  wordMilestoneProgress,
} from "@/lib/learningProgress";

const FEEDBACK_EMAIL = process.env.NEXT_PUBLIC_FEEDBACK_EMAIL ?? "";
const LEARNING_STREAK_STORAGE_KEY = "mandarinflow:learning-streak";
const HOME_FEATURES: HomeFeature[] = [
  {
    description: "Học tiếng Trung trực tiếp qua video và phụ đề.",
    href: "#videos",
    icon: BookOpen,
    iconClassName: "bg-rose-100 text-rose-700",
    title: "Học qua ngữ cảnh",
  },
  {
    description: "Nhấn vào từ để xem nghĩa, pinyin và cách đọc.",
    icon: Search,
    iconClassName: "bg-amber-100 text-amber-700",
    title: "Tra cứu nhanh",
  },
  {
    description: "Lưu từ mới để xem lại và xây dựng vốn từ mỗi ngày.",
    href: "/vocabulary",
    icon: Bookmark,
    iconClassName: "bg-emerald-100 text-emerald-700",
    title: "Lưu từ vựng",
  },
  {
    description: "Theo dõi từ đã lưu, video đã học và chuỗi ngày học.",
    icon: ChartNoAxesColumnIncreasing,
    iconClassName: "bg-violet-100 text-violet-700",
    title: "Theo dõi tiến độ",
  },
];

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
  const tabletTagMenuRef = useRef<HTMLDetailsElement>(null);
  const shouldReduceMotion = useReducedMotion();
  const [videos, setVideos] = useState<ImportedVideo[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedWordCounts, setSavedWordCounts] = useState<Record<string, number>>({});
  const [videoProgress, setVideoProgress] = useState<Record<string, VideoProgress>>({});
  const [dailyStats, setDailyStats] = useState({ savedWords: 0, watchedVideos: 0 });
  const [learningStreak, setLearningStreak] = useState(1);
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
        setVideos(shuffleVideos(videoItems));
        setSavedWordCounts(countSavedWordsByVideo(vocabularyItems));
        setVideoProgress(Object.fromEntries(progressItems.map((item) => [item.youtube_video_id, item])));
        const streakResult = updateLearningStreak();
        setLearningStreak(streakResult.streak);
        const savedWordsToday = countWordsSavedToday(vocabularyItems);
        notifyLearningProgress(vocabularyItems.length, false, savedWordsToday);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        setDailyStats({
          savedWords: savedWordsToday,
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

  useEffect(() => {
    function handleProgress(event: Event) {
      const detail = (event as CustomEvent<LearningProgressDetail>).detail;
      if (!Number.isFinite(detail?.savedWordsToday)) return;
      setDailyStats((current) => ({ ...current, savedWords: detail.savedWordsToday! }));
    }

    window.addEventListener(LEARNING_PROGRESS_EVENT, handleProgress);
    const latestProgress = readLatestLearningProgress();
    const restoreTimeout = Number.isFinite(latestProgress?.savedWordsToday)
      ? window.setTimeout(
          () => setDailyStats((current) => ({ ...current, savedWords: latestProgress!.savedWordsToday! })),
          0,
        )
      : null;
    return () => {
      window.removeEventListener(LEARNING_PROGRESS_EVENT, handleProgress);
      if (restoreTimeout !== null) window.clearTimeout(restoreTimeout);
    };
  }, []);

  useEffect(() => {
    let refreshing = false;

    async function refreshVocabularyProgress() {
      if (refreshing || document.visibilityState === "hidden") return;
      refreshing = true;
      try {
        const vocabularyItems = await listVocabulary();
        setSavedWordCounts(countSavedWordsByVideo(vocabularyItems));
        setDailyStats((current) => ({
          ...current,
          savedWords: countWordsSavedToday(vocabularyItems),
        }));
      } catch {
        // The initial page request remains responsible for displaying load errors.
      } finally {
        refreshing = false;
      }
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "visible") void refreshVocabularyProgress();
    }

    window.addEventListener("focus", refreshVocabularyProgress);
    window.addEventListener("pageshow", refreshVocabularyProgress);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("focus", refreshVocabularyProgress);
      window.removeEventListener("pageshow", refreshVocabularyProgress);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
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
    const visible = tagOptions.slice(0, 3);
    const selectedOption = tagOptions.find((tag) => tag.toLocaleLowerCase("vi") === selectedTag.toLocaleLowerCase("vi"));

    if (selectedOption && !visible.includes(selectedOption)) visible[visible.length - 1] = selectedOption;

    return {
      visible,
      overflow: tagOptions.filter((tag) => !visible.includes(tag)),
    };
  }, [selectedTag, tagOptions]);
  const tabletTagOptions = useMemo(() => {
    const selectedOption = tagOptions.find((tag) => tag.toLocaleLowerCase("vi") === selectedTag.toLocaleLowerCase("vi"));
    const visible = [selectedOption ?? tagOptions[0]];

    return {
      visible,
      overflow: tagOptions.filter((tag) => !visible.includes(tag)),
    };
  }, [selectedTag, tagOptions]);
  const filteredVideos = useMemo(() => filterVideos(videos, selectedTag, query), [query, selectedTag, videos]);
  const pagination = useMemo(() => paginateVideos(filteredVideos, requestedPage), [filteredVideos, requestedPage]);
  const savedWordsToday = dailyStats.savedWords;
  const nextMilestone = nextWordMilestone(savedWordsToday);
  const progress = Math.min(Math.max(wordMilestoneProgress(savedWordsToday), 0), 100);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.log({ savedWords: savedWordsToday, nextMilestone, progress });
    }
  }, [nextMilestone, progress, savedWordsToday]);

  useEffect(() => {
    if (!loading && pagination.page !== requestedPage) {
      router.replace(videoCatalogUrl(selectedTag, pagination.page), { scroll: false });
    }
  }, [loading, pagination.page, requestedPage, router, selectedTag]);

  function selectTag(tag: string) {
    tagMenuRef.current?.removeAttribute("open");
    tabletTagMenuRef.current?.removeAttribute("open");
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
      <section className="mx-auto max-w-7xl px-3 py-4 sm:p-4">
        <div className="mb-6 sm:mb-8">
          <div className="flex flex-col gap-4 sm:gap-5 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0 flex-1">
              <div className="mb-3 inline-flex max-w-full items-center gap-1.5 rounded-full border border-brand-200 bg-brand-100/80 px-3 py-1.5 text-xs font-semibold text-brand-800 sm:mb-4 sm:gap-2 sm:px-4 sm:text-sm">
                <Sparkles size={15} className="shrink-0 text-brand-500 sm:h-4 sm:w-4" />
                Học qua ngữ cảnh video có sẵn
              </div>
              <AnimatedBrandTitle />
              <p className="mt-2 text-sm leading-6 text-slate-500 sm:text-base sm:leading-7">
                Chọn video và học tiếng Trung thông qua tương tác trực tiếp.
              </p>
              <div className="scrollbar-none -mx-3 mt-4 flex w-[calc(100%+1.5rem)] items-stretch justify-start gap-2.5 overflow-x-auto px-3 pb-1 md:mx-0 md:w-fit md:max-w-[390px] md:flex-wrap md:overflow-visible md:px-0 md:pb-0 xl:max-w-none xl:flex-nowrap">
                {HOME_FEATURES.map((feature) => (
                  <HomeFeatureCard feature={feature} key={feature.title} />
                ))}
              </div>
            </div>
            <div className="w-full overflow-hidden rounded-xl border border-cream-200 bg-cream-50 px-3 py-3 shadow-sm sm:rounded-2xl sm:px-4 md:w-[calc((100%-2rem)/3)] md:self-stretch">
              <div className="mb-2 flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wider text-brand-700">
                <span className="flex min-w-0 items-center gap-2">
                <CalendarDays size={15} />
                <span>Daily Learning Stats</span>
                </span>
                <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#fff1d6] px-2 py-1 text-[11px] normal-case text-[#a65a20]">
                  <Flame size={13} fill="currentColor" />
                  {learningStreak} ngày
                </span>
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
              <div className="mt-3 border-t border-cream-200 pt-2.5">
                <div className="mb-1.5 flex items-center justify-between gap-3 text-[11px] text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <PartyPopper size={13} className="text-brand-700" />
                    Mốc pháo hoa tiếp theo
                  </span>
                  <strong className="text-brand-800">{nextMilestone} từ</strong>
                </div>
                <div
                  aria-label={`${savedWordsToday} trên ${nextMilestone} từ`}
                  aria-valuemax={100}
                  aria-valuemin={0}
                  aria-valuenow={progress}
                  className="h-2 w-full overflow-hidden rounded-full bg-brand-100"
                  role="progressbar"
                >
                  <div
                    className="h-full rounded-full bg-brand-500 transition-[width] duration-300 ease-out"
                    data-testid="daily-word-progress-fill"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          className="mb-5 grid scroll-mt-20 gap-3 md:grid-cols-3 md:items-center md:gap-4"
          data-route-scroll-anchor
          id="videos"
        >
          <div className="order-2 min-w-0 flex-1 md:order-1" aria-label="Lọc video theo chủ đề">
            <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700 md:hidden">
              <Tags size={17} className="text-brand-700" />
              <span>Lọc theo chủ đề</span>
            </div>
            <div className="scrollbar-none -mx-3 flex w-[calc(100%+1.5rem)] gap-2 overflow-x-auto px-3 pb-1 md:hidden">
              {tagOptions.map((tag) => (
                <TagFilterButton key={tag} tag={tag} selectedTag={selectedTag} onSelect={selectTag} />
              ))}
            </div>
            <div className="hidden h-12 min-w-0 items-center gap-2 md:flex lg:hidden">
              <Tags size={16} className="shrink-0 text-brand-700" aria-label="Lọc theo chủ đề" />
              {tabletTagOptions.visible.map((tag) => (
                <TagFilterButton key={tag} tag={tag} selectedTag={selectedTag} onSelect={selectTag} />
              ))}
              {tabletTagOptions.overflow.length > 0 ? (
                <details className="group relative shrink-0" ref={tabletTagMenuRef}>
                  <summary
                    aria-label="Xem thêm chủ đề"
                    className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full border border-cream-300 bg-cream-50 text-slate-600 transition hover:border-brand-300 hover:text-brand-800 [&::-webkit-details-marker]:hidden"
                  >
                    <ChevronDown className="transition-transform group-open:rotate-180" size={16} />
                  </summary>
                  <div className="absolute left-0 top-11 z-20 min-w-40 rounded-lg border border-cream-200 bg-cream-50 p-1.5 shadow-lg">
                    {tabletTagOptions.overflow.map((tag) => {
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
          {!loading && !error && filteredVideos.length > 6 ? (
            <nav className="order-3 hidden items-center justify-center gap-2 md:order-2 md:flex" aria-label="Phân trang video">
              <button
                aria-label="Trang trước"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-cream-300 bg-cream-50 text-brand-800 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!pagination.hasPrevious}
                onClick={() => selectPage(pagination.page - 1)}
                type="button"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="min-w-16 text-center text-sm font-semibold text-slate-700">
                {pagination.page} / {pagination.totalPages}
              </span>
              <button
                aria-label="Trang sau"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-cream-300 bg-cream-50 text-brand-800 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!pagination.hasNext}
                onClick={() => selectPage(pagination.page + 1)}
                type="button"
              >
                <ChevronRight size={18} />
              </button>
            </nav>
          ) : (
            <span className="order-3 hidden md:order-2 md:block" aria-hidden="true" />
          )}
          <label className="relative order-1 block w-full min-w-0 md:order-3">
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
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3" aria-label="Đang tải video">
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
            className="grid gap-4 sm:grid-cols-2 md:grid-cols-3"
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
                className="overflow-hidden rounded-2xl border border-cream-200 bg-cream-50 shadow-sm transition hover:border-brand-200 hover:shadow-md sm:rounded-3xl"
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
                        sizes="(min-width: 768px) 33vw, (min-width: 640px) 50vw, 100vw"
                        src={getPreferredYouTubeThumbnail(video.youtube_video_id, video.thumbnail_url) ?? video.thumbnail_url}
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center font-serif text-5xl font-bold text-cream-50">汉</div>
                    )}
                    <div className="absolute inset-x-2 bottom-2 flex items-center justify-between gap-2 text-[11px] font-medium text-brand-950 sm:inset-x-3 sm:text-sm">
                      {formatVideoDuration(video.duration_seconds) ? (
                        <span className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-lg border border-white/60 bg-cream-50/90 px-2 py-1 shadow-sm backdrop-blur-md">
                          <Clock3 className="text-brand-800" size={16} strokeWidth={1.8} />
                          <span>{formatVideoDuration(video.duration_seconds)}</span>
                        </span>
                      ) : null}
                      <span className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-lg border border-white/60 bg-[#edf3ef]/95 px-2 py-1 font-semibold text-[#365b45] shadow-sm backdrop-blur-md">
                        <BookOpen className="shrink-0" size={16} strokeWidth={1.8} />
                        <span>Đã lưu {savedWordCounts[video.youtube_video_id] ?? 0} từ</span>
                      </span>
                    </div>
                  </div>
                </Link>
                <div className="w-full p-[14px] sm:p-[18px]">
                  <Link className="line-clamp-2 min-h-10 text-sm font-bold leading-tight text-brand-950 hover:text-brand-700 sm:min-h-12 sm:text-base" href={watchHref}>
                    {video.title}
                  </Link>
                  <div className="mt-2 flex min-h-5 items-center justify-between gap-2 text-xs text-slate-500 sm:gap-3 sm:text-sm">
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
          <nav className="mt-5 flex items-center justify-center gap-2 md:hidden" aria-label="Phân trang video">
            <button
              aria-label="Trang trước"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-cream-300 bg-cream-50 text-brand-800 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!pagination.hasPrevious}
              onClick={() => selectPage(pagination.page - 1)}
              type="button"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="min-w-16 text-center text-sm font-semibold text-slate-700">
              {pagination.page} / {pagination.totalPages}
            </span>
            <button
              aria-label="Trang sau"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-cream-300 bg-cream-50 text-brand-800 transition hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!pagination.hasNext}
              onClick={() => selectPage(pagination.page + 1)}
              type="button"
            >
              <ChevronRight size={18} />
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
    return <h1 className="text-3xl font-bold leading-tight tracking-normal text-slate-800 sm:text-4xl lg:text-5xl">{title}</h1>;
  }

  return (
    <h1 aria-label={title} className="text-3xl font-bold leading-tight tracking-normal text-slate-800 sm:text-4xl lg:text-5xl">
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

function updateLearningStreak(): { shouldCelebrate: boolean; streak: number } {
  const today = localDateKey(new Date());

  try {
    const stored = window.localStorage.getItem(LEARNING_STREAK_STORAGE_KEY);
    const previous = stored ? (JSON.parse(stored) as LearningStreakRecord) : null;

    if (previous?.lastVisit === today) {
      return { shouldCelebrate: false, streak: Math.max(previous.streak, 1) };
    }

    const isConsecutive = previous ? daysBetween(previous.lastVisit, today) === 1 : false;
    const streak = isConsecutive ? previous!.streak + 1 : 1;
    const shouldCelebrate = streak === 2 && previous?.lastCelebratedStreak !== 2;
    const nextRecord: LearningStreakRecord = {
      lastCelebratedStreak: shouldCelebrate ? 2 : isConsecutive ? previous?.lastCelebratedStreak ?? 0 : 0,
      lastVisit: today,
      streak,
    };
    window.localStorage.setItem(LEARNING_STREAK_STORAGE_KEY, JSON.stringify(nextRecord));
    return { shouldCelebrate, streak };
  } catch {
    return { shouldCelebrate: false, streak: 1 };
  }
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function daysBetween(start: string, end: string): number {
  const startTime = Date.parse(`${start}T00:00:00Z`);
  const endTime = Date.parse(`${end}T00:00:00Z`);
  return Math.round((endTime - startTime) / 86_400_000);
}

type LearningStreakRecord = {
  lastCelebratedStreak: number;
  lastVisit: string;
  streak: number;
};

type HomeFeature = {
  description: string;
  href?: string;
  icon: LucideIcon;
  iconClassName: string;
  title: string;
};

function HomeFeatureCard({ feature }: { feature: HomeFeature }) {
  const Icon = feature.icon;
  const className =
    "flex h-[75px] w-[190px] shrink-0 items-center gap-2 rounded-xl border border-cream-200 bg-cream-50 p-2 shadow-sm transition-colors";
  const content = (
    <>
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${feature.iconClassName}`}>
        <Icon aria-hidden="true" size={17} strokeWidth={1.9} />
      </span>
      <span className="min-w-0">
        <strong className="block text-xs font-semibold leading-4 text-slate-800">{feature.title}</strong>
        <span className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">{feature.description}</span>
      </span>
    </>
  );

  if (feature.href) {
    const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
      if (!feature.href?.startsWith("#") || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }

      const target = document.getElementById(feature.href.slice(1));
      if (!target) return;

      event.preventDefault();
      window.history.replaceState(window.history.state, "", feature.href);
      target.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    };

    return (
      <Link
        className={`${className} cursor-pointer hover:border-brand-200 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200`}
        href={feature.href}
        onClick={handleClick}
      >
        {content}
      </Link>
    );
  }

  return <article className={className}>{content}</article>;
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

function shuffleVideos(videos: ImportedVideo[]): ImportedVideo[] {
  const shuffled = [...videos];

  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[randomIndex]] = [shuffled[randomIndex], shuffled[index]];
  }

  return shuffled;
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
