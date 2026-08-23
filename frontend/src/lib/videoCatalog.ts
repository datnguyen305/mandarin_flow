import type { ImportedVideo } from "@/types";

export const ALL_VIDEO_TAGS = "All";
export const VIDEO_PAGE_SIZE = 6;

export function formatVideoDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return null;
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainingSeconds = totalSeconds % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function getVideoTags(videos: ImportedVideo[]): string[] {
  const tags = new Map<string, string>();
  for (const video of videos) {
    for (const rawTag of video.tags ?? []) {
      const tag = rawTag.trim();
      const key = tag.toLocaleLowerCase("vi");
      if (tag && !tags.has(key)) tags.set(key, tag);
    }
  }
  return Array.from(tags.values()).sort((left, right) => left.localeCompare(right, "vi"));
}

export function filterVideos(videos: ImportedVideo[], selectedTag: string, query = ""): ImportedVideo[] {
  const normalizedQuery = query.trim().toLocaleLowerCase("vi");
  const normalizedTag = selectedTag.toLocaleLowerCase("vi");

  return videos.filter((video) => {
    const matchesTag =
      selectedTag === ALL_VIDEO_TAGS ||
      (video.tags ?? []).some((tag) => tag.toLocaleLowerCase("vi") === normalizedTag);
    const matchesQuery =
      !normalizedQuery ||
      video.title.toLocaleLowerCase("vi").includes(normalizedQuery) ||
      video.youtube_video_id.toLocaleLowerCase("vi").includes(normalizedQuery);
    return matchesTag && matchesQuery;
  });
}

export function paginateVideos(videos: ImportedVideo[], requestedPage: number, pageSize = VIDEO_PAGE_SIZE) {
  const totalPages = Math.max(1, Math.ceil(videos.length / pageSize));
  const page = Math.min(Math.max(Math.trunc(requestedPage) || 1, 1), totalPages);
  const start = (page - 1) * pageSize;
  return {
    items: videos.slice(start, start + pageSize),
    page,
    totalPages,
    hasPrevious: page > 1,
    hasNext: page < totalPages,
  };
}

export function parseVideoPage(value: string | null): number {
  if (!value) return 1;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

export function videoCatalogUrl(tag: string, page: number): string {
  const params = new URLSearchParams();
  if (tag !== ALL_VIDEO_TAGS) params.set("tag", tag);
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/?${query}` : "/";
}
