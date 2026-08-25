import { describe, expect, it } from "vitest";
import { buildWeeklyLearningActivity, milestoneTimelinePosition } from "./DailyLearningStats";

describe("DailyLearningStats helpers", () => {
  it.each([
    [0, 0],
    [1, 5],
    [4, 20],
    [5, 25],
    [9, 45],
    [10, 50],
    [20, 75],
    [35, 100],
  ])("maps %i saved words to %i%% of the displayed timeline", (savedWords, expected) => {
    expect(milestoneTimelinePosition(savedWords)).toBe(expected);
  });

  it("builds a rolling seven-day series from real vocabulary timestamps", () => {
    const result = buildWeeklyLearningActivity(
      [
        { created_at: "2026-08-19T10:00:00" },
        { created_at: "2026-08-24T10:00:00" },
        { created_at: "2026-08-25T08:00:00" },
        { created_at: "2026-08-25T09:00:00" },
      ],
      new Date("2026-08-25T12:00:00"),
    );

    expect(result).toHaveLength(7);
    expect(result.map((day) => day.count)).toEqual([1, 0, 0, 0, 0, 1, 2]);
    expect(result.at(-1)).toMatchObject({ count: 2, isToday: true, label: "T3" });
  });

  it("ignores invalid timestamps", () => {
    const result = buildWeeklyLearningActivity([{ created_at: "invalid" }], new Date("2026-08-25T12:00:00"));
    expect(result.every((day) => day.count === 0)).toBe(true);
  });
});
