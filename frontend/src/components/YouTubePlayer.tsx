"use client";

import { forwardRef, useEffect, useImperativeHandle } from "react";
import { dispatchGlobalPlayerCommand, GLOBAL_PLAYER_ANCHOR_ID } from "@/lib/globalYouTubePlayer";

export interface YouTubePlayerHandle {
  getCurrentTime: () => number;
  seekTo: (seconds: number) => void;
  pause: () => void;
}

interface Props {
  videoId: string;
  startTime?: number;
}

export const YouTubePlayer = forwardRef<YouTubePlayerHandle, Props>(function YouTubePlayer({ videoId, startTime = 0 }, ref) {
  useImperativeHandle(ref, () => ({
    getCurrentTime: () => window.fluentMandarinPlayer?.getCurrentTime() ?? 0,
    seekTo: (seconds: number) => {
      window.fluentMandarinPlayer?.seekTo(seconds);
      dispatchGlobalPlayerCommand({ type: "seek", seconds });
    },
    pause: () => {
      window.fluentMandarinPlayer?.pause();
      dispatchGlobalPlayerCommand({ type: "pause" });
    },
  }));

  useEffect(() => {
    dispatchGlobalPlayerCommand({ type: "load", videoId, startTime });
  }, [videoId, startTime]);

  return <div className="aspect-video w-full overflow-hidden rounded-md bg-black" id={GLOBAL_PLAYER_ANCHOR_ID} />;
});

