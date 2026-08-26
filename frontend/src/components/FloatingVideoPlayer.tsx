"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ExternalLink, X } from "lucide-react";
import { CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FLOATING_VIDEO_HIDDEN_KEY,
  GLOBAL_PLAYER_ANCHOR_ID,
  GLOBAL_PLAYER_EVENT,
  LAST_WATCH_HREF_KEY,
  type GlobalPlayerCommand,
} from "@/lib/globalYouTubePlayer";

declare global {
  interface Window {
    YT?: typeof YT;
  }
}

const FLOATING_STYLE: CSSProperties = {
  bottom: 12,
  right: 12,
};

export function FloatingVideoPlayer() {
  const pathname = usePathname();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<YT.Player | null>(null);
  const loadedVideoIdRef = useRef<string | null>(null);
  const pendingLoadRef = useRef<{ videoId: string; startTime: number } | null>(null);
  const [href, setHref] = useState<string | null>(null);
  const [hidden, setHidden] = useState(true);
  const [anchorStyle, setAnchorStyle] = useState<CSSProperties | null>(null);

  const watchVideo = useMemo(() => parseWatchHref(href), [href]);
  const dockedInWatch = pathname === "/watch" && Boolean(watchVideo);
  const visible = Boolean(watchVideo) && (!hidden || dockedInWatch);

  useEffect(() => {
    function sync() {
      setHref(window.localStorage.getItem(LAST_WATCH_HREF_KEY));
      setHidden(window.localStorage.getItem(FLOATING_VIDEO_HIDDEN_KEY) === "1");
    }

    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("last-watch-updated", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("last-watch-updated", sync);
    };
  }, []);

  useEffect(() => {
    const api = {
      getCurrentTime: () => playerRef.current?.getCurrentTime() ?? 0,
      seekTo: (seconds: number) => playerRef.current?.seekTo(seconds, true),
      pause: () => playerRef.current?.pauseVideo(),
    };
    window.fluentMandarinPlayer = api;
    return () => {
      if (window.fluentMandarinPlayer === api) {
        delete window.fluentMandarinPlayer;
      }
    };
  }, []);

  const createPlayer = useCallback(() => {
    if (!containerRef.current || playerRef.current || !window.YT?.Player || !pendingLoadRef.current) return;
    const pending = pendingLoadRef.current;
    containerRef.current.replaceChildren();
    const playerHost = document.createElement("div");
    playerHost.style.width = "100%";
    playerHost.style.height = "100%";
    containerRef.current.appendChild(playerHost);

    playerRef.current = new window.YT.Player(playerHost, {
      videoId: pending.videoId,
      playerVars: {
        start: Math.floor(pending.startTime),
        rel: 0,
        modestbranding: 1,
        playsinline: 1,
        enablejsapi: 1,
        origin: window.location.origin,
      },
      width: "100%",
      height: "100%",
    });
    loadedVideoIdRef.current = pending.videoId;
    pendingLoadRef.current = null;
  }, []);

  const loadVideo = useCallback((videoId: string, startTime: number) => {
    if (!containerRef.current) {
      pendingLoadRef.current = { videoId, startTime };
      return;
    }

    if (playerRef.current) {
      if (loadedVideoIdRef.current !== videoId) {
        playerRef.current.loadVideoById({ videoId, startSeconds: Math.floor(startTime) });
        loadedVideoIdRef.current = videoId;
      }
      return;
    }

    pendingLoadRef.current = { videoId, startTime };
    if (window.YT?.Player) {
      createPlayer();
      return;
    }

    if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
      const script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      document.body.appendChild(script);
    }

    const timer = window.setInterval(() => {
      if (window.YT?.Player) {
        window.clearInterval(timer);
        createPlayer();
      }
    }, 100);
    window.setTimeout(() => window.clearInterval(timer), 10000);
  }, [createPlayer]);

  useEffect(() => {
    function handleCommand(event: Event) {
      const command = (event as CustomEvent<GlobalPlayerCommand>).detail;
      if (command.type === "load" && command.videoId) {
        loadVideo(command.videoId, command.startTime ?? 0);
      }
      if (command.type === "seek" && command.seconds != null) {
        playerRef.current?.seekTo(command.seconds, true);
      }
      if (command.type === "pause") {
        playerRef.current?.pauseVideo();
      }
    }

    window.addEventListener(GLOBAL_PLAYER_EVENT, handleCommand);
    return () => window.removeEventListener(GLOBAL_PLAYER_EVENT, handleCommand);
  }, [loadVideo]);

  useEffect(() => {
    if (!watchVideo) return;
    loadVideo(watchVideo.videoId, watchVideo.startTime);
  }, [loadVideo, watchVideo]);

  useEffect(() => {
    let animationFrame = 0;

    function updateAnchorRect() {
      if (!dockedInWatch) {
        setAnchorStyle(null);
        return;
      }
      const anchor = document.getElementById(GLOBAL_PLAYER_ANCHOR_ID);
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      setAnchorStyle({
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
      });
    }

    updateAnchorRect();
    const scheduleAnchorUpdate = () => {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(updateAnchorRect);
    };
    window.addEventListener("resize", scheduleAnchorUpdate);
    window.addEventListener("scroll", scheduleAnchorUpdate, true);
    window.visualViewport?.addEventListener("resize", scheduleAnchorUpdate);
    const anchor = document.getElementById(GLOBAL_PLAYER_ANCHOR_ID);
    const observer = anchor ? new ResizeObserver(scheduleAnchorUpdate) : null;
    if (anchor && observer) observer.observe(anchor);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", scheduleAnchorUpdate);
      window.removeEventListener("scroll", scheduleAnchorUpdate, true);
      window.visualViewport?.removeEventListener("resize", scheduleAnchorUpdate);
      observer?.disconnect();
    };
  }, [dockedInWatch]);

  function close() {
    playerRef.current?.pauseVideo();
    window.localStorage.setItem(FLOATING_VIDEO_HIDDEN_KEY, "1");
    setHidden(true);
  }

  const style = dockedInWatch && anchorStyle ? anchorStyle : FLOATING_STYLE;

  return (
    <aside
      aria-hidden={!visible}
      className={`fixed z-40 w-[280px] max-w-[calc(100vw-24px)] overflow-hidden border border-cream-200 bg-black shadow-2xl sm:w-[320px] ${
        dockedInWatch ? "transition-none" : "transition-[left,top,width,height,bottom,right] duration-300"
      } ${
        visible ? "" : "invisible pointer-events-none"
      } ${
        dockedInWatch ? "rounded-md" : "rounded-lg"
      }`}
      style={style}
    >
      {!dockedInWatch && href ? (
        <div className="flex items-center justify-between gap-2 border-b border-cream-200 bg-cream-100 px-2 py-1.5">
          <Link className="inline-flex min-w-0 items-center gap-1.5 truncate text-xs font-semibold text-brand-800 hover:text-brand-900" href={href}>
            <ExternalLink size={14} />
            Quay lại video
          </Link>
          <button aria-label="Đóng video nổi" className="rounded-md p-1 text-slate-500 hover:bg-cream-200" onClick={close} type="button">
            <X size={16} />
          </button>
        </div>
      ) : null}
      <div className={dockedInWatch ? "h-full w-full" : "aspect-video w-full"} ref={containerRef} />
    </aside>
  );
}

function parseWatchHref(href: string | null) {
  if (!href || typeof window === "undefined") return null;
  const url = new URL(href, window.location.origin);
  const videoId = url.searchParams.get("v");
  if (!videoId) return null;
  const startTime = Number(url.searchParams.get("t") ?? 0);
  return { videoId, startTime: Number.isFinite(startTime) ? startTime : 0 };
}
