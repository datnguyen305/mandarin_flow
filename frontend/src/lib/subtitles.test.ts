import { describe, expect, it } from "vitest";
import { convertChineseText } from "./chinese-script";
import { extractYouTubeId, findActiveSubtitleIndex, mergeSubtitleBatch } from "./subtitles";

const subtitles = [
  { start: 1, end: 3, text: "我", translation: "tôi", tokens: [] },
  { start: 3, end: 5, text: "医院", translation: "bệnh viện", tokens: [] }
];

describe("findActiveSubtitleIndex", () => {
  it("uses start <= currentTime < end", () => {
    expect(findActiveSubtitleIndex(subtitles, 1)).toBe(0);
    expect(findActiveSubtitleIndex(subtitles, 2.9)).toBe(0);
    expect(findActiveSubtitleIndex(subtitles, 3)).toBe(1);
    expect(findActiveSubtitleIndex(subtitles, 5)).toBe(-1);
  });

  it("finds subtitles in sorted arrays with binary search semantics", () => {
    const many = Array.from({ length: 100 }, (_, index) => ({
      start: index * 10,
      end: index * 10 + 8,
      text: `${index}`,
      translation: null,
      tokens: []
    }));

    expect(findActiveSubtitleIndex(many, 805)).toBe(80);
    expect(findActiveSubtitleIndex(many, 808)).toBe(-1);
  });
});

describe("extractYouTubeId", () => {
  it("extracts ids from common YouTube URLs", () => {
    expect(extractYouTubeId("https://www.youtube.com/watch?v=abc123abc12")).toBe("abc123abc12");
    expect(extractYouTubeId("https://youtu.be/abc123abc12?t=10")).toBe("abc123abc12");
  });
});

describe("mergeSubtitleBatch", () => {
  it("merges, deduplicates by id, and preserves timestamp order", () => {
    const merged = mergeSubtitleBatch(
      [
        { id: 2, start: 3, end: 5, text: "医院", translation: "old", tokens: [], processing_status: "raw" },
        { id: 1, start: 1, end: 3, text: "我", translation: null, tokens: [], processing_status: "raw" }
      ],
      {
        video_id: "abc123abc12",
        batch_index: 0,
        start_time: 0,
        end_time: 120,
        subtitles: [{ id: 2, start: 3, end: 5, text: "医院", translation: "bệnh viện", tokens: [], processing_status: "processed" }]
      }
    );

    expect(merged.map((subtitle) => subtitle.id)).toEqual([1, 2]);
    expect(merged[1].translation).toBe("bệnh viện");
    expect(merged[1].processing_status).toBe("processed");
  });
});

describe("saved vocabulary review URLs", () => {
  it("returns to the saved timestamp on the watch page", () => {
    const youtubeVideoId = "abc123abc12";
    const timestamp = 125.8;

    expect(`/watch?v=${youtubeVideoId}&t=${Math.floor(timestamp)}`).toBe("/watch?v=abc123abc12&t=125");
  });
});

describe("Chinese script conversion", () => {
  it("converts simplified subtitle text to traditional Chinese", () => {
    expect(convertChineseText("这个视频有中文字幕。", "traditional")).toBe("這個視頻有中文字幕。");
  });

  it("converts traditional subtitle text back to simplified Chinese", () => {
    expect(convertChineseText("這個視頻有中文字幕。", "simplified")).toBe("这个视频有中文字幕。");
  });
});
