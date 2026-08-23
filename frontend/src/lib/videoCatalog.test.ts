import { describe, expect, it } from "vitest";
import type { ImportedVideo } from "@/types";
import {
  ALL_VIDEO_TAGS,
  filterVideos,
  formatVideoDuration,
  getVideoTags,
  paginateVideos,
  parseVideoPage,
  videoCatalogUrl,
} from "./videoCatalog";

describe("formatVideoDuration", () => {
  it("formats short and long videos", () => {
    expect(formatVideoDuration(202)).toBe("3:22");
    expect(formatVideoDuration(3723)).toBe("1:02:03");
  });

  it("returns null when duration is unavailable", () => {
    expect(formatVideoDuration(null)).toBeNull();
    expect(formatVideoDuration(Number.NaN)).toBeNull();
  });
});

function videos(count: number, tags: string[] = []): ImportedVideo[] {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    youtube_video_id: `video-${index + 1}`,
    title: `Video ${index + 1}`,
    url: `https://youtube.com/watch?v=video-${index + 1}`,
    thumbnail_url: null,
    language: "zh",
    processing_status: "completed",
    tags,
    created_at: "2026-08-22T00:00:00Z",
  }));
}

describe("video catalog pagination", () => {
  it.each([
    [4, 1, 4],
    [6, 1, 6],
    [7, 2, 1],
    [14, 3, 2],
  ])("paginates %i videos into the expected last page", (count, page, expectedItems) => {
    const result = paginateVideos(videos(count), page);
    expect(result.items).toHaveLength(expectedItems);
    expect(result.page).toBe(page);
    expect(result.totalPages).toBe(Math.ceil(count / 6));
  });

  it("clamps pages to valid boundaries", () => {
    expect(paginateVideos(videos(14), 0).page).toBe(1);
    expect(paginateVideos(videos(14), 99).page).toBe(3);
  });
});

describe("video tag filtering", () => {
  const items = [
    ...videos(7, ["Du lịch"]),
    { ...videos(1, ["Podcast"])[0], id: 20, youtube_video_id: "podcast", title: "Chinese Podcast" },
  ];

  it("returns all videos for All and more than one page for a large tag", () => {
    expect(filterVideos(items, ALL_VIDEO_TAGS)).toHaveLength(8);
    expect(paginateVideos(filterVideos(items, "Du lịch"), 1).totalPages).toBe(2);
  });

  it("returns an empty list for a tag without videos", () => {
    expect(filterVideos(items, "Ẩm thực")).toEqual([]);
  });

  it("filters tags case-insensitively and combines them with search", () => {
    expect(filterVideos(items, "podcast")).toHaveLength(1);
    expect(filterVideos(items, ALL_VIDEO_TAGS, "Chinese")).toHaveLength(1);
  });

  it("deduplicates available tags case-insensitively", () => {
    expect(getVideoTags([...items, ...videos(1, ["du lịch"])])).toEqual(["Du lịch", "Podcast"]);
  });
});

describe("video catalog URL state", () => {
  it("omits default state and keeps selected tag/page", () => {
    expect(videoCatalogUrl(ALL_VIDEO_TAGS, 1)).toBe("/");
    expect(videoCatalogUrl("Du lịch", 2)).toBe("/?tag=Du+l%E1%BB%8Bch&page=2");
  });

  it("falls back to page one for invalid URL values", () => {
    expect(parseVideoPage(null)).toBe(1);
    expect(parseVideoPage("0")).toBe(1);
    expect(parseVideoPage("abc")).toBe(1);
    expect(parseVideoPage("3")).toBe(3);
  });
});
