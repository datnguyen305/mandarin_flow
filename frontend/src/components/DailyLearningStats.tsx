"use client";

import { CalendarDays, Flame, PartyPopper } from "lucide-react";
import { nextWordMilestone, wordMilestoneProgress } from "@/lib/learningProgress";

type DailyLearningStatsProps = {
  learningStreak: number;
  savedWordsToday: number;
  weeklyActivity: WeeklyLearningDay[];
};

export type WeeklyLearningDay = {
  count: number;
  dateKey: string;
  isToday: boolean;
  label: string;
};

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
      label: date.getDay() === 0 ? "CN" : `T${date.getDay() + 1}`,
    };
  });
}

export function DailyLearningStats({ learningStreak, savedWordsToday, weeklyActivity }: DailyLearningStatsProps) {
  const normalizedWords = Math.max(0, savedWordsToday);
  const nextMilestone = nextWordMilestone(normalizedWords);
  const progress = Math.min(Math.max(wordMilestoneProgress(normalizedWords), 0), 100);
  const maxWeeklyCount = Math.max(1, ...weeklyActivity.map((day) => day.count));

  return (
    <section className="flex h-full w-full flex-col overflow-hidden rounded-xl border border-cream-200 bg-cream-50 px-3 py-3 shadow-sm sm:rounded-2xl sm:px-4">
      <header className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold uppercase tracking-wider text-brand-700">
        <span className="flex min-w-0 flex-1 items-center justify-start gap-2 text-left">
          <CalendarDays aria-hidden="true" size={16} />
          <span className="truncate">Daily Learning Stats</span>
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#fff1d6] px-2 py-1 text-[11px] normal-case text-[#a65a20]">
          <Flame aria-hidden="true" fill="currentColor" size={13} />
          {learningStreak} ngày
        </span>
      </header>

      <section className="mt-2" aria-label="Số từ đã lưu trong 7 ngày gần nhất">
        <div className="mb-1.5 flex items-center justify-between gap-3 text-[11px] text-slate-500">
          <span className="font-semibold">Từ đã lưu trong tuần</span>
          <span>7 ngày gần nhất</span>
        </div>
        <div className="flex h-[72px] items-end justify-between gap-2">
          {weeklyActivity.map((day) => {
            const barHeight = day.count === 0 ? 5 : Math.max(13, Math.round((day.count / maxWeeklyCount) * 43));
            return (
              <div className="flex min-w-0 flex-1 flex-col items-center justify-end" key={day.dateKey}>
                <span className="mb-1 text-[9px] font-semibold leading-none text-slate-500">{day.count}</span>
                <span
                  aria-label={`${day.label}: ${day.count} từ`}
                  className={`w-full max-w-6 rounded-t-md transition-[height] duration-300 ${
                    day.isToday ? "bg-brand-500" : "bg-brand-200"
                  }`}
                  style={{ height: `${barHeight}px` }}
                />
                <span className={`mt-1 text-[9px] leading-none ${day.isToday ? "font-semibold text-brand-800" : "text-slate-500"}`}>
                  {day.label}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <div className="mt-auto border-t border-cream-200 pt-2.5">
        <div className="mb-1.5 flex items-center justify-between gap-3 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <PartyPopper aria-hidden="true" className="text-brand-700" size={13} />
            Mốc pháo hoa tiếp theo
          </span>
          <strong className="text-brand-800">{nextMilestone} từ</strong>
        </div>
        <div
          aria-label={`${normalizedWords} trên ${nextMilestone} từ`}
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
    </section>
  );
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
