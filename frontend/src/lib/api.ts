import type { DictionaryEntry, ImportedVideo, ProcessingProgress, SavedVocabulary, SubtitleResponse, VideoProgress } from "@/types";

// An empty base URL keeps browser requests on the current origin. Next.js
// rewrites /api/* to the internal Go API, which also works behind a domain.
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function resolveApiBaseUrl(configuredUrl: string): string {
  if (typeof window === "undefined") {
    return configuredUrl;
  }

  if (!configuredUrl) return "";

  const apiUrl = new URL(configuredUrl);
  const pageHostname = window.location.hostname;
  const localHostnames = new Set(["localhost", "127.0.0.1"]);
  if (localHostnames.has(apiUrl.hostname) && localHostnames.has(pageHostname)) {
    apiUrl.hostname = pageHostname;
    return apiUrl.toString().replace(/\/$/, "");
  }

  return configuredUrl.replace(/\/$/, "");
}

const API_BASE_URL = resolveApiBaseUrl(configuredApiBaseUrl);
export { API_BASE_URL };

export class DevAccessError extends Error {}
export class NetworkRequestError extends Error {}
export class ApiRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

async function requestError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  const message = body?.error?.message ?? body?.detail ?? `Request failed with ${response.status}`;
  const code = body?.error?.code;
  if (response.status === 403) return new DevAccessError(message);
  return new ApiRequestError(message, response.status, code);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {})
      },
      credentials: "include",
      cache: "no-store"
    });
  } catch (error) {
    throw new NetworkRequestError(error instanceof Error ? error.message : "Không thể kết nối đến máy chủ.");
  }
  if (!response.ok) {
    throw await requestError(response);
  }
  return response.json() as Promise<T>;
}

function devHeaders(devToken?: string | null): HeadersInit {
  return devToken ? { "X-Dev-Token": devToken } : {};
}

export async function processVideo(url: string, devToken?: string | null, tags: string[] = []): Promise<ProcessingProgress> {
  return request("/api/videos/process", {
    method: "POST",
    headers: devHeaders(devToken),
    body: JSON.stringify({ url, source_language: "zh", target_language: "vi", tags })
  });
}

export type AssistantChatMessage = { role: "user" | "assistant"; content: string };

export async function chatWithAssistant(
  message: string,
  history: AssistantChatMessage[],
  devToken?: string | null,
): Promise<{ reply: string; youtube_url: string | null; imported_video_id?: string | null; import_status?: string | null; pending_action?: { name: string; arguments: { youtube_url: string }; requires_approval: boolean } | null }> {
  return request("/api/agent/chat", {
    method: "POST",
    headers: devHeaders(devToken),
    body: JSON.stringify({ message, history }),
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

export async function getProcessingProgress(videoId: string): Promise<ProcessingProgress> {
  return request(`/api/videos/${encodeURIComponent(videoId)}/processing-progress`);
}

export async function listVideos(limit = 50, devToken?: string | null): Promise<ImportedVideo[]> {
  return request(`/api/videos?limit=${limit}`, { headers: devHeaders(devToken) });
}

export async function verifyDevAccess(devToken: string): Promise<void> {
  await request("/api/dev/verify", { headers: devHeaders(devToken) });
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
    throw await requestError(response);
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

export async function lookupWord(word: string, context?: string, pinyin?: string | null): Promise<DictionaryEntry> {
  const params = new URLSearchParams();
  if (context) params.set("context", context);
  if (pinyin) params.set("pinyin", pinyin);
  const query = params.size ? `?${params.toString()}` : "";
  return request(`/api/dictionary/${encodeURIComponent(word)}${query}`);
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
