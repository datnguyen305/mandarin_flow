import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DictionaryPanel } from "./DictionaryPanel";
import type { DictionaryEntry, SubtitleLine, SubtitleToken } from "@/types";

vi.mock("@/components/HanziStrokeWriter", () => ({
  HanziStrokeWriter: ({ text }: { text: string }) => <div data-testid="stroke-order">Stroke {text}</div>,
}));

const token: SubtitleToken = { text: "字幕", pinyin: "zìmù", meaning: "phụ đề" };
const subtitle: SubtitleLine = {
  id: 1,
  start: 0,
  end: 2,
  text: "字幕提供者-SnoW°笨兔",
  translation: "Người cung cấp phụ đề...",
  tokens: [token],
};

const baseProps = {
  anchorRef: { current: null },
  token,
  loading: false,
  error: null,
  subtitle,
  onClose: vi.fn(),
  onPause: vi.fn(),
  onSave: vi.fn(),
  saving: false,
  saveStatus: null,
  script: "simplified" as const,
};

describe("DictionaryPanel", () => {
  it("renders multiple meanings as separate senses", () => {
    render(<DictionaryPanel {...baseProps} entry={entry()} />);

    expect(screen.getByText("① phụ đề")).toBeTruthy();
    expect(screen.getByText("② chú thích")).toBeTruthy();
    expect(screen.getByText("Phần chữ hiển thị trên video hoặc phim.")).toBeTruthy();
  });

  it("does not render the contextual phrase section", () => {
    render(<DictionaryPanel {...baseProps} entry={entry()} />);

    expect(screen.queryByText("Trong câu này")).toBeNull();
    expect(screen.queryByText("字幕提供者")).toBeNull();
  });

  it("renders collocations and examples", () => {
    render(<DictionaryPanel {...baseProps} entry={entry()} />);

    expect(screen.getByText("中文字幕")).toBeTruthy();
    expect(screen.getByText("zhōngwén zìmù")).toBeTruthy();
    expect(screen.getByText("这个视频有中文字幕。")).toBeTruthy();
    expect(screen.getByText("Video này có phụ đề tiếng Trung.")).toBeTruthy();
  });

  it("does not crash when enrichment lists are missing", () => {
    render(<DictionaryPanel {...baseProps} entry={{ word: "字幕", pinyin: "zìmù", meaning: "phụ đề" }} />);

    expect(screen.getByText("phụ đề")).toBeTruthy();
    expect(screen.getAllByTestId("stroke-order").length).toBeGreaterThan(0);
    expect(screen.getByText("Lưu từ")).toBeTruthy();
  });

  it("shows basic meaning without the removed contextual enrichment error", () => {
    render(<DictionaryPanel {...baseProps} entry={{ word: "字幕", pinyin: "zìmù", meaning: "phụ đề", enrichment_error: "Không thể tải thêm giải thích." }} />);

    expect(screen.getByText("phụ đề")).toBeTruthy();
    expect(screen.queryByText("Không thể tải thêm giải thích.")).toBeNull();
  });

  it("renders Chinese content using the selected subtitle script", () => {
    render(
      <DictionaryPanel
        {...baseProps}
        entry={{ word: "視頻", pinyin: "shìpín", meaning: "video" }}
        subtitle={{ ...subtitle, text: "這個視頻很好。" }}
        token={{ text: "視頻", pinyin: "shìpín", meaning: "video" }}
      />,
    );

    expect(screen.getByRole("heading", { name: "视频" })).toBeTruthy();
    expect(screen.getByText("这个视频很好。" )).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "視頻" })).toBeNull();
  });
});

function entry(): DictionaryEntry {
  return {
    word: "字幕",
    pinyin: "zìmù",
    meaning: "phụ đề; chú thích",
    part_of_speech: "danh từ",
    meanings: [
      { meaning: "phụ đề", definition: "Phần chữ hiển thị trên video hoặc phim." },
      { meaning: "chú thích", definition: "Nội dung chữ được hiển thị để giải thích." },
    ],
    context: {
      original_sentence: "字幕提供者-SnoW°笨兔",
      selected_meaning: "phụ đề",
      phrase: "字幕提供者",
      phrase_pinyin: "zìmù tígōngzhě",
      phrase_meaning: "người cung cấp phụ đề",
      explanation: 'Trong cụm này, 字幕 mang nghĩa "phụ đề".',
    },
    collocations: [{ text: "中文字幕", pinyin: "zhōngwén zìmù", meaning: "phụ đề tiếng Trung" }],
    examples: [{ chinese: "这个视频有中文字幕。", pinyin: "Zhège shìpín yǒu Zhōngwén zìmù.", vietnamese: "Video này có phụ đề tiếng Trung." }],
  };
}
