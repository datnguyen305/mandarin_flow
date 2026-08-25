"use client";

import {
  Bookmark,
  CalendarDays,
  ChevronRight,
  Clock3,
  Flame,
  Lightbulb,
  PartyPopper,
  Target,
  Video,
} from "lucide-react";
import { nextWordMilestone } from "@/lib/learningProgress";

export const DISPLAYED_WORD_MILESTONES = [0, 5, 10, 20, 30] as const;

export type WeeklyLearningDay = {
  count: number;
  dateKey: string;
  isToday: boolean;
  label: string;
};

type DailyLearningStatsProps = {
  learningStreak: number;
  savedWordsToday: number;
  studyMinutesToday?: number;
  watchedVideosToday: number;
  weeklyActivity: WeeklyLearningDay[];
};

export function milestoneTimelinePosition(savedWords: number): number {
  const normalized = Math.max(0, savedWords);
  const milestones = DISPLAYED_WORD_MILESTONES;
  if (normalized >= milestones[milestones.length - 1]) return 100;

  for (let index = 0; index < milestones.length - 1; index += 1) {
    const start = milestones[index];
    const end = milestones[index + 1];
    if (normalized <= end) {
      const segmentProgress = (normalized - start) / (end - start);
      return ((index + segmentProgress) / (milestones.length - 1)) * 100;
    }
  }

  return 100;
}

export function buildWeeklyLearningActivity(
  items: Array<{ created_at: string }>,
  now = new Date(),
): WeeklyLearningDay[] {
  const counts = new Map<string, number>();
  items.forEach((item) => {
    const date = new Date(item.created_at);
    if (Number.isNaN(date.getTime())) return;
    const key = localDateKey(date);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });

  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(now);
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() - (6 - index));
    const dateKey = localDateKey(date);
    return {
      count: counts.get(dateKey) ?? 0,
      dateKey,
      isToday: index === 6,
      label: weekdayLabel(date.getDay()),
    };
  });
}

export function DailyLearningStats({
  learningStreak,
  savedWordsToday,
  studyMinutesToday = 0,
  watchedVideosToday,
  weeklyActivity,
}: DailyLearningStatsProps) {
  const normalizedWords = Math.max(0, savedWordsToday);
  const nextMilestone = nextWordMilestone(normalizedWords);
  const remainingWords = Math.max(0, nextMilestone - normalizedWords);
  const dailyGoalProgress = Math.min((normalizedWords / Math.max(nextMilestone, 1)) * 100, 100);
  const timelinePosition = milestoneTimelinePosition(normalizedWords);
  const maxWeeklyCount = Math.max(1, ...weeklyActivity.map((day) => day.count));

  return (
    <section className="flex h-full w-full flex-col overflow-hidden rounded-2xl border border-cream-200 bg-cream-50 p-4 shadow-sm sm:p-5">
      <header className="flex min-h-11 items-center justify-between gap-3 border-b border-cream-200 pb-3">
        <span className="flex min-w-0 items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-700">
          <CalendarDays aria-hidden="true" size={16} />
          <span className="truncate">Daily Learning Stats</span>
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#fff1d6] px-2.5 py-1.5 text-xs font-semibold text-[#a65a20]">
          <Flame aria-hidden="true" fill="currentColor" size={14} />
          {learningStreak} ngày
          <ChevronRight aria-hidden="true" size={13} />
        </span>
      </header>

      <div className="grid grid-cols-2 py-4">
        <Metric icon={Bookmark} label="Từ đã lưu hôm nay" value={normalizedWords} />
        <Metric className="border-l border-cream-200 pl-4" icon={Video} label="Video đã học hôm nay" value={watchedVideosToday} />
      </div>

      <section className="border-t border-cream-200 pt-4">
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="inline-flex items-center gap-2 font-semibold text-slate-600">
            <PartyPopper aria-hidden="true" className="text-brand-700" size={15} />
            Mốc pháo hoa tiếp theo
          </span>
          <strong className="shrink-0 text-brand-800">{nextMilestone} từ</strong>
        </div>

        <div className="scrollbar-none mt-3 overflow-x-auto pb-1">
          <div className="min-w-[350px] px-3 pt-8">
            <div
              aria-label={`${normalizedWords} trên ${nextMilestone} từ`}
              aria-valuemax={nextMilestone}
              aria-valuemin={0}
              aria-valuenow={Math.min(normalizedWords, nextMilestone)}
              className="relative h-12"
              role="progressbar"
            >
              <div className="absolute inset-x-0 top-3 h-1 rounded-full bg-cream-200" />
              <div
                className="absolute left-0 top-3 h-1 rounded-full bg-brand-500 transition-[width] duration-300 ease-out"
                data-testid="daily-word-progress-fill"
                style={{ width: `${timelinePosition}%` }}
              />

              <span
                className="absolute top-0 z-10 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-cream-50 bg-brand-700 shadow-sm transition-[left] duration-300 ease-out"
                style={{ left: `${timelinePosition}%` }}
              />
              <span
                className="absolute top-[-30px] -translate-x-1/2 whitespace-nowrap rounded-md bg-brand-800 px-2 py-1 text-[10px] font-semibold text-cream-50 shadow-sm transition-[left] duration-300 ease-out"
                style={{ left: `${Math.min(Math.max(timelinePosition, 8), 92)}%` }}
              >
                {normalizedWords} / {nextMilestone} từ
              </span>

              {DISPLAYED_WORD_MILESTONES.map((milestone, index) => {
                const left = (index / (DISPLAYED_WORD_MILESTONES.length - 1)) * 100;
                const reached = normalizedWords >= milestone;
                const accent = milestoneAccent(milestone);
                return (
                  <span className="absolute top-0 -translate-x-1/2" key={milestone} style={{ left: `${left}%` }}>
                    {milestone >= 10 ? (
                      <PartyPopper aria-hidden="true" className={`absolute -top-5 left-1/2 -translate-x-1/2 ${accent}`} size={12} />
                    ) : null}
                    <span
                      className={`block h-7 w-7 rounded-full border-4 border-cream-50 shadow-sm ${
                        reached ? "bg-brand-500" : "bg-cream-200"
                      }`}
                    />
                    <span className="absolute left-1/2 top-8 -translate-x-1/2 text-[10px] font-semibold text-slate-500">{milestone}</span>
                  </span>
                );
              })}
            </div>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">Lưu thêm {remainingWords} từ để đạt mốc tiếp theo</p>
      </section>

      <div className="mt-4 grid gap-3 border-t border-cream-200 pt-4 xl:grid-cols-[minmax(0,0.4fr)_minmax(0,0.6fr)]">
        <div className="grid grid-cols-2 gap-2">
          <MiniStat
            icon={Clock3}
            label="Thời gian học hôm nay"
            secondary="Chưa có dữ liệu"
            value={`${Math.max(0, studyMinutesToday)} phút`}
          />
          <MiniStat
            icon={Target}
            label="Mục tiêu ngày"
            secondary={`${normalizedWords}/${nextMilestone} từ`}
            value={`${Math.round(dailyGoalProgress)}%`}
          />
        </div>

        <section className="min-h-[120px] rounded-xl border border-cream-200 bg-cream-100/55 p-3">
          <h3 className="text-xs font-semibold text-slate-700">7 ngày qua</h3>
          <div className="mt-3 flex h-[86px] items-end justify-between gap-1.5">
            {weeklyActivity.map((day) => {
              const barHeight = day.count === 0 ? 8 : Math.max(16, Math.round((day.count / maxWeeklyCount) * 58));
              return (
                <div className="flex min-w-0 flex-1 flex-col items-center justify-end" key={day.dateKey}>
                  <span className="mb-1 text-[9px] font-semibold text-slate-500">{day.count}</span>
                  <span
                    className={`w-full max-w-5 rounded-t-md ${day.isToday ? "bg-brand-500" : "bg-brand-200"}`}
                    style={{ height: `${barHeight}px` }}
                  />
                  <span className={`mt-1 text-[9px] ${day.isToday ? "font-semibold text-brand-800" : "text-slate-500"}`}>{day.label}</span>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      <footer className="mt-3 flex items-start gap-2 rounded-lg bg-brand-50 px-3 py-2 text-[11px] leading-4 text-slate-600">
        <Lightbulb aria-hidden="true" className="mt-0.5 shrink-0 text-brand-700" size={14} />
        <span>Mẹo: Học mỗi ngày một chút để tiến bộ dài lâu!</span>
      </footer>
    </section>
  );
}

function Metric({
  className = "pr-4",
  icon: Icon,
  label,
  value,
}: {
  className?: string;
  icon: typeof Bookmark;
  label: string;
  value: number;
}) {
  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <Icon aria-hidden="true" size={16} />
        </span>
        <strong className="text-2xl leading-none text-slate-800">{value}</strong>
      </div>
      <p className="mt-1.5 text-[11px] leading-4 text-slate-500">{label}</p>
    </div>
  );
}

function MiniStat({
  icon: Icon,
  label,
  secondary,
  value,
}: {
  icon: typeof Clock3;
  label: string;
  secondary: string;
  value: string;
}) {
  return (
    <section className="min-h-[120px] rounded-xl border border-cream-200 bg-cream-100/55 p-3">
      <Icon aria-hidden="true" className="text-brand-700" size={17} />
      <strong className="mt-2 block text-lg leading-none text-slate-800">{value}</strong>
      <p className="mt-2 text-[11px] font-medium leading-4 text-slate-600">{label}</p>
      <p className="mt-1 text-[10px] leading-4 text-slate-400">{secondary}</p>
    </section>
  );
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function weekdayLabel(day: number): string {
  return day === 0 ? "CN" : `T${day + 1}`;
}

function milestoneAccent(milestone: number): string {
  if (milestone >= 30) return "text-violet-500";
  if (milestone >= 20) return "text-sky-500";
  return "text-emerald-600";
}
