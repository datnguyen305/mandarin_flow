import OpenCC from "opencc-js";

export type ChineseScript = "simplified" | "traditional";

const simplifiedToTraditional = OpenCC.Converter({ from: "cn", to: "tw" });
const traditionalToSimplified = OpenCC.Converter({ from: "tw", to: "cn" });

export function convertChineseText(text: string, script: ChineseScript): string {
  if (!text) return text;
  return script === "traditional" ? simplifiedToTraditional(text) : traditionalToSimplified(text);
}
