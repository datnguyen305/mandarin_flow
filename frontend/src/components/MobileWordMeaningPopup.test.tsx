import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MobileWordMeaningPopup } from "./MobileWordMeaningPopup";

const baseProps = {
  entry: { word: "視頻", pinyin: "shìpín", meaning: "video", meanings: [{ meaning: "video" }, { meaning: "đoạn phim" }] },
  error: null,
  loading: false,
  onClose: vi.fn(),
  onSave: vi.fn(),
  saveStatus: null,
  saving: false,
  script: "simplified" as const,
  token: { text: "視頻", pinyin: "shìpín", meaning: "video" },
};

describe("MobileWordMeaningPopup", () => {
  it("shows the selected script, meanings, and save action", async () => {
    render(<MobileWordMeaningPopup {...baseProps} />);

    expect(await screen.findByRole("heading", { name: "视频" })).toBeTruthy();
    expect(screen.getByText("1. video")).toBeTruthy();
    expect(screen.getByText("2. đoạn phim")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Lưu từ" }));
    expect(baseProps.onSave).toHaveBeenCalledOnce();
  });
});
