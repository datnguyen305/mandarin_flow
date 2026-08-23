const YOUTUBE_THUMBNAIL_PATTERN = /https?:\/\/(?:img|i)\.youtube\.com\/vi\/[^/]+\/[^/]+\.jpg/i;

export function getPreferredYouTubeThumbnail(videoId: string, fallbackUrl?: string | null): string | null {
  if (!videoId && !fallbackUrl) return null;
  return videoId ? `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg` : fallbackUrl ?? null;
}

export function isYouTubeThumbnailUrl(value: string | null | undefined): boolean {
  return Boolean(value && YOUTUBE_THUMBNAIL_PATTERN.test(value));
}
