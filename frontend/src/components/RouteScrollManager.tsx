"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { scrollBelowAppHeader } from "@/lib/scroll";

export function RouteScrollManager() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const shouldReduceMotion = useReducedMotion();
  const previousRouteRef = useRef<string | null>(null);
  const routeKey = `${pathname}?${searchParams.toString()}`;

  useEffect(() => {
    if (previousRouteRef.current === null) {
      previousRouteRef.current = routeKey;
      return;
    }
    if (previousRouteRef.current === routeKey) return;
    previousRouteRef.current = routeKey;

    const frame = window.requestAnimationFrame(() => {
      const anchor = document.querySelector<HTMLElement>("[data-route-scroll-anchor]");
      if (anchor) {
        scrollBelowAppHeader(anchor, shouldReduceMotion ? "auto" : "smooth");
        return;
      }
      window.scrollTo({ top: 0, behavior: shouldReduceMotion ? "auto" : "smooth" });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [routeKey, shouldReduceMotion]);

  return null;
}
