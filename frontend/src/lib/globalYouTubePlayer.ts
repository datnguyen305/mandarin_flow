export const LAST_WATCH_HREF_KEY = "fluentmandarin:last-watch-href";
export const FLOATING_VIDEO_HIDDEN_KEY = "fluentmandarin:floating-video-hidden";
export const GLOBAL_PLAYER_ANCHOR_ID = "global-youtube-player-anchor";
export const GLOBAL_PLAYER_EVENT = "global-youtube-player-command";

export interface GlobalPlayerCommand {
  type: "load" | "seek" | "pause";
  videoId?: string;
  startTime?: number;
  seconds?: number;
}

export interface GlobalYouTubePlayerApi {
  getCurrentTime: () => number;
  seekTo: (seconds: number) => void;
  pause: () => void;
}

declare global {
  interface Window {
    fluentMandarinPlayer?: GlobalYouTubePlayerApi;
  }
}

export function dispatchGlobalPlayerCommand(command: GlobalPlayerCommand) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(GLOBAL_PLAYER_EVENT, { detail: command }));
}

