export const LEARNING_PROGRESS_EVENT = "mandarinflow:learning-progress";
export const LEARNING_PROGRESS_BROADCAST_KEY = "mandarinflow:learning-progress-broadcast";
export const WORD_MILESTONE_SIZE = 5;

export type LearningProgressDetail = {
  eventId: string;
  savedNow?: boolean;
  savedWordsToday?: number;
  totalSavedWords: number;
};

export function notifyLearningProgress(totalSavedWords: number, savedNow = false, savedWordsToday?: number): void {
  const detail: LearningProgressDetail = {
    eventId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    savedNow,
    savedWordsToday,
    totalSavedWords,
  };
  window.dispatchEvent(
    new CustomEvent<LearningProgressDetail>(LEARNING_PROGRESS_EVENT, {
      detail,
    }),
  );

  if (Number.isFinite(savedWordsToday)) {
    try {
      window.localStorage.setItem(LEARNING_PROGRESS_BROADCAST_KEY, JSON.stringify(detail));
    } catch {
      // The active tab still receives the custom event when storage is unavailable.
    }
  }
}

export function countWordsSavedToday(items: Array<{ created_at: string }>, now = new Date()): number {
  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  return items.filter((item) => new Date(item.created_at) >= startOfToday).length;
}

export function readLatestLearningProgress(): LearningProgressDetail | null {
  try {
    const stored = window.localStorage.getItem(LEARNING_PROGRESS_BROADCAST_KEY);
    if (!stored) return null;
    const detail = JSON.parse(stored) as LearningProgressDetail;
    if (!detail.eventId || !Number.isFinite(detail.totalSavedWords)) return null;
    return detail;
  } catch {
    return null;
  }
}

export function completedWordMilestone(totalWords: number): number {
  return Math.floor(Math.max(0, totalWords) / WORD_MILESTONE_SIZE) * WORD_MILESTONE_SIZE;
}

export function reachedWordMilestone(totalWords: number): boolean {
  return totalWords >= WORD_MILESTONE_SIZE && totalWords % WORD_MILESTONE_SIZE === 0;
}

export function nextWordMilestone(totalWords: number): number {
  const normalized = Math.max(0, totalWords);
  return (Math.floor(normalized / WORD_MILESTONE_SIZE) + 1) * WORD_MILESTONE_SIZE;
}

export function wordMilestoneProgress(totalWords: number): number {
  const normalized = Math.max(0, totalWords);
  if (normalized > 0 && normalized % WORD_MILESTONE_SIZE === 0) return 100;
  return ((normalized % WORD_MILESTONE_SIZE) / WORD_MILESTONE_SIZE) * 100;
}
