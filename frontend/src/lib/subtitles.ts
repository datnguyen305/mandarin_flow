import type { SubtitleBatch, SubtitleLine } from "@/types";

export function findActiveSubtitleIndex(subtitles: SubtitleLine[], currentTime: number): number {
  let low = 0;
  let high = subtitles.length - 1;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const subtitle = subtitles[middle];
    if (subtitle.start <= currentTime && currentTime < subtitle.end) return middle;
    if (currentTime < subtitle.start) high = middle - 1;
    else low = middle + 1;
  }
  return -1;
}

export function mergeSubtitleBatch(current: SubtitleLine[], batch: SubtitleBatch): SubtitleLine[] {
  const byKey = new Map<string, SubtitleLine>();
  for (const subtitle of current) {
    byKey.set(subtitle.id != null ? `id:${subtitle.id}` : `time:${subtitle.start}:${subtitle.end}:${subtitle.text}`, subtitle);
  }
  for (const subtitle of batch.subtitles) {
    byKey.set(subtitle.id != null ? `id:${subtitle.id}` : `time:${subtitle.start}:${subtitle.end}:${subtitle.text}`, subtitle);
  }
  return [...byKey.values()].sort((a, b) => a.start - b.start || a.end - b.end);
}

export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remainingSeconds = total % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

export function extractYouTubeId(url: string): string | null {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace("www.", "");
    if (host === "youtube.com" || host === "m.youtube.com") {
      if (parsed.pathname === "/watch") return parsed.searchParams.get("v");
      if (parsed.pathname.startsWith("/shorts/") || parsed.pathname.startsWith("/embed/")) {
        return parsed.pathname.split("/").filter(Boolean).at(-1) ?? null;
      }
    }
    if (host === "youtu.be") return parsed.pathname.split("/").filter(Boolean)[0] ?? null;
    return null;
  } catch {
    return null;
  }
}
