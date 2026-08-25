"use client";

import { PartyPopper } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  LEARNING_PROGRESS_BROADCAST_KEY,
  LEARNING_PROGRESS_EVENT,
  reachedWordMilestone,
  type LearningProgressDetail,
} from "@/lib/learningProgress";

export function LearningCelebrationProvider() {
  const shouldReduceMotion = useReducedMotion();
  const [message, setMessage] = useState<string | null>(null);
  const particles = useMemo(() => createParticles(), []);
  const lastEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    function celebrate(detail: LearningProgressDetail | null | undefined) {
      if (!detail || detail.eventId === lastEventIdRef.current) return;
      lastEventIdRef.current = detail.eventId;
      const savedWordsToday = detail.savedWordsToday;
      if (!detail.savedNow || !Number.isFinite(savedWordsToday)) return;
      if (reachedWordMilestone(savedWordsToday!)) {
        setMessage(`Tuyệt vời! Hôm nay bạn đã lưu được ${savedWordsToday} từ.`);
      }
    }

    function handleProgress(event: Event) {
      celebrate((event as CustomEvent<LearningProgressDetail>).detail);
    }

    function handleStorage(event: StorageEvent) {
      if (event.key !== LEARNING_PROGRESS_BROADCAST_KEY || !event.newValue) return;
      try {
        const detail = JSON.parse(event.newValue) as LearningProgressDetail;
        celebrate(detail);
        window.dispatchEvent(new CustomEvent<LearningProgressDetail>(LEARNING_PROGRESS_EVENT, { detail }));
      } catch {
        // Ignore malformed cross-tab events.
      }
    }

    window.addEventListener(LEARNING_PROGRESS_EVENT, handleProgress);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener(LEARNING_PROGRESS_EVENT, handleProgress);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(() => setMessage(null), 4200);
    return () => window.clearTimeout(timeout);
  }, [message]);

  return (
    <AnimatePresence>
      {message ? (
        <motion.div
          animate={{ opacity: 1 }}
          className="pointer-events-none fixed inset-0 z-[100] overflow-hidden"
          exit={{ opacity: 0 }}
          initial={{ opacity: 0 }}
        >
          {particles.map((particle, index) => (
                <motion.span
                  animate={{
                    opacity: [0, 1, 1, 0],
                    rotate: index % 2 === 0 ? 260 : -260,
                    scale: [0.5, 1, 0.75],
                    x: particle.x,
                    y: particle.y,
                  }}
                  className="absolute h-3 w-2 rounded-sm"
                  initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
                  key={index}
                  style={{ backgroundColor: particle.color, left: particle.left, top: particle.top }}
                  transition={{
                    delay: shouldReduceMotion ? 0 : particle.delay,
                    duration: shouldReduceMotion ? 0.35 : 1.55,
                    ease: "easeOut",
                  }}
                />
              ))}
          <motion.div
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="absolute left-1/2 top-20 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-center gap-3 rounded-xl border border-brand-200 bg-cream-50 px-4 py-3 text-brand-900 shadow-xl"
            exit={{ opacity: 0, scale: 0.96, y: -12 }}
            initial={{ opacity: 0, scale: 0.94, y: -16 }}
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#fff1d6] text-[#a65a20]">
              <PartyPopper size={21} />
            </span>
            <p className="text-sm font-semibold leading-5">{message}</p>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function createParticles() {
  const colors = ["#3d6346", "#e3a13b", "#cf6f5b", "#6f9fc2", "#8d79bd"];
  return Array.from({ length: 56 }, (_, index) => {
    const side = index % 2 === 0 ? 1 : -1;
    const spread = 90 + (index % 8) * 24;
    return {
      color: colors[index % colors.length],
      delay: (index % 10) * 0.025,
      left: side === 1 ? "18%" : "82%",
      top: `${58 + (index % 5) * 5}%`,
      x: side * spread * (0.35 + (index % 7) / 7),
      y: -180 - (index % 9) * 35,
    };
  });
}
