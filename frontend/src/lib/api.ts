import type { DictionaryEntry, ImportedVideo, ProcessingProgress, SavedVocabulary, SubtitleResponse, VideoProgress } from "@/types";

const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function resolveApiBaseUrl(configuredUrl: string): string {
  if (typeof window === "undefined") {
    return configuredUrl;
  }

  const apiUrl = new URL(configuredUrl);
  const pageHostname = window.location.hostname;
  const localHostnames = new Set(["localhost", "127.0.0.1"]);
  if (localHostnames.has(apiUrl.hostname) && localHostnames.has(pageHostname)) {
    return "";
  }

  return configuredUrl.replace(/\/$/, "");
}

const API_BASE_URL = resolveApiBaseUrl(configuredApiBaseUrl);
export { API_BASE_URL };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    credentials: "include",
    cache: "no-store"
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function devHeaders(devToken?: string | null): HeadersInit {
  return devToken ? { "X-Dev-Token": devToken } : {};
}

export async function processVideo(url: string, devToken?: string | null): Promise<ProcessingProgress> {
  return request("/api/videos/process", {
    method: "POST",
    headers: devHeaders(devToken),
    body: JSON.stringify({ url, source_language: "zh", target_language: "vi" })
  });
}

export async function uploadYouTubeCookies(content: string, devToken?: string | null): Promise<{ status: string; path: string }> {
  return request("/api/videos/cookies", {
    method: "POST",
    headers: devHeaders(devToken),
    body: JSON.stringify({ content })
  });
}

export async function getSubtitles(videoId: string): Promise<SubtitleResponse> {
  return request(`/api/videos/${videoId}/subtitles`);
}

export async function getRawSubtitles(videoId: string): Promise<SubtitleResponse> {
  return request(`/api/videos/${videoId}/subtitles/raw`);
}

export async function listVideos(limit = 50, devToken?: string | null): Promise<ImportedVideo[]> {
  return request(`/api/videos?limit=${limit}`, { headers: devHeaders(devToken) });
}

export async function listVideoProgress(): Promise<VideoProgress[]> {
  return request("/api/videos/progress");
}

export async function deleteVideo(videoId: string, devToken?: string | null): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/videos/${encodeURIComponent(videoId)}`, {
    method: "DELETE",
    headers: devHeaders(devToken),
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `Request failed with ${response.status}`);
  }
}

export async function updatePlaybackPosition(videoId: string, currentTime: number): Promise<void> {
  await request(`/api/videos/${encodeURIComponent(videoId)}/playback-position`, {
    method: "POST",
    body: JSON.stringify({ current_time: currentTime })
  });
}

export async function retrySubtitleBatch(videoId: string, batchIndex: number): Promise<void> {
  await request(`/api/videos/${encodeURIComponent(videoId)}/batches/${batchIndex}/retry`, { method: "POST" });
}

export async function lookupWord(word: string, context?: string): Promise<DictionaryEntry> {
  const params = context ? `?context=${encodeURIComponent(context)}` : "";
  return request(`/api/dictionary/${encodeURIComponent(word)}${params}`);
}

export async function saveVocabulary(payload: {
  word: string;
  pinyin?: string | null;
  meaning?: string | null;
  youtube_video_id: string;
  subtitle_id: number;
  timestamp: number;
}): Promise<{ id: number; status: string }> {
  return request("/api/vocabulary", { method: "POST", body: JSON.stringify(payload) });
}

export async function listVocabulary(): Promise<SavedVocabulary[]> {
  return request("/api/vocabulary");
}

export async function deleteVocabulary(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/${id}`, { method: "DELETE", credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `Request failed with ${response.status}`);
  }
}
