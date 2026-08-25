import { beforeEach, describe, expect, it } from "vitest";
import {
  completedWordMilestone,
  countWordsSavedToday,
  LEARNING_PROGRESS_BROADCAST_KEY,
  nextWordMilestone,
  notifyLearningProgress,
  readLatestLearningProgress,
  reachedWordMilestone,
  wordMilestoneProgress,
} from "./learningProgress";

describe("learning progress", () => {
  beforeEach(() => window.localStorage.clear());

  it("calculates progress toward five-word milestones", () => {
    expect(wordMilestoneProgress(0)).toBe(0);
    expect(wordMilestoneProgress(1)).toBe(20);
    expect(wordMilestoneProgress(2)).toBe(40);
    expect(wordMilestoneProgress(4)).toBe(80);
    expect(wordMilestoneProgress(5)).toBe(100);
    expect(wordMilestoneProgress(11)).toBe(20);
    expect(nextWordMilestone(4)).toBe(5);
    expect(nextWordMilestone(5)).toBe(10);
    expect(nextWordMilestone(10)).toBe(15);
    expect(wordMilestoneProgress(10)).toBe(100);
    expect(wordMilestoneProgress(15)).toBe(100);
    expect(wordMilestoneProgress(20)).toBe(100);
  });

  it("only celebrates exact five-word milestones", () => {
    expect(reachedWordMilestone(4)).toBe(false);
    expect(reachedWordMilestone(5)).toBe(true);
    expect(reachedWordMilestone(6)).toBe(false);
    expect(reachedWordMilestone(10)).toBe(true);
  });

  it("calculates the latest completed milestone", () => {
    expect(completedWordMilestone(6)).toBe(5);
  });

  it("persists the latest save so a remounted page can recover progress", () => {
    notifyLearningProgress(6, true, 2);
    expect(readLatestLearningProgress()).toMatchObject({ savedNow: true, savedWordsToday: 2, totalSavedWords: 6 });
    expect(window.localStorage.getItem(LEARNING_PROGRESS_BROADCAST_KEY)).toBeTruthy();
  });

  it("counts only vocabulary saved since local midnight", () => {
    const now = new Date("2026-08-25T12:00:00");
    expect(
      countWordsSavedToday(
        [{ created_at: "2026-08-24T23:59:59" }, { created_at: "2026-08-25T00:00:00" }, { created_at: "2026-08-25T09:30:00" }],
        now,
      ),
    ).toBe(2);
  });
});
