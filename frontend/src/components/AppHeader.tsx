"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BookOpen, Home, Library, Palette, Search } from "lucide-react";
import { type MouseEvent, useEffect, useState, useSyncExternalStore } from "react";
import { HOME_VIDEOS_REFRESH_EVENT } from "@/lib/home-videos";
import { scrollBelowAppHeader } from "@/lib/scroll";

const THEME_KEY = "fluentmandarin:pastel-theme";
const THEME_EVENT = "pastel-theme-updated";

const navItems = [
  { href: "/", label: "Trang chủ", icon: Home },
  { href: "/", label: "Video", icon: Library, watchOnly: true },
  { href: "/dictionary", label: "Tra từ", icon: Search },
  { href: "/vocabulary", label: "Từ vựng", icon: BookOpen }
];

const themes = [
  { id: "sage", label: "Sage", color: "#e3ebe4" },
  { id: "mint", label: "Mint", color: "#d5f0e5" },
  { id: "sky", label: "Sky", color: "#d9ebf7" },
  { id: "rose", label: "Rose", color: "#f9e0e6" },
  { id: "lavender", label: "Lavender", color: "#e6e0f7" }
];

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const theme = useSyncExternalStore(subscribeTheme, getThemeSnapshot, getServerThemeSnapshot);
  const visibleNavItems = navItems.filter((item) => !item.watchOnly || pathname === "/watch");
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  function handleThemeChange(themeId: string) {
    window.localStorage.setItem(THEME_KEY, themeId);
    window.dispatchEvent(new CustomEvent(THEME_EVENT));
  }

  function refreshHomeVideos(event: MouseEvent<HTMLAnchorElement>) {
    if (pathname !== "/" || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    event.preventDefault();
    window.dispatchEvent(new CustomEvent(HOME_VIDEOS_REFRESH_EVENT));
    router.replace("/#videos", { scroll: false });
    window.requestAnimationFrame(() => {
      const target = document.getElementById("videos");
      if (target) {
        scrollBelowAppHeader(target, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
      }
    });
  }

  return (
    <header className="sticky top-0 z-30 border-b border-cream-200 bg-cream-50/90 backdrop-blur" data-app-header>
      <nav className="relative mx-auto flex max-w-7xl flex-nowrap items-center justify-between gap-2 px-3 py-2 sm:gap-3 sm:px-4 sm:py-3">
        <Link
          aria-label="Làm mới video đề xuất"
          className="flex min-w-0 shrink-0 items-center gap-3 text-left"
          href="/#videos"
          onClick={refreshHomeVideos}
          title="Làm mới video đề xuất"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-700 font-serif text-lg font-bold text-cream-50 shadow-sm">
            汉
          </span>
          <span className="hidden min-w-0 sm:block">
            <span className="block truncate text-base font-bold leading-none text-brand-900">MandarinFlow</span>
            <span className="mt-1 block truncate text-xs font-medium text-slate-500">Học tiếng Trung qua video</span>
          </span>
        </Link>

        <div
          className={`grid w-auto shrink-0 gap-1 rounded-xl bg-cream-200/70 p-1 text-sm font-medium text-slate-600 lg:absolute lg:left-1/2 lg:-translate-x-1/2 ${
            visibleNavItems.length === 4 ? "grid-cols-4" : "grid-cols-3"
          }`}
        >
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const href = item.href;
            const active = item.watchOnly ? pathname === "/watch" : item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                aria-label={item.label}
                className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 transition ${
                  active ? "bg-cream-50 font-semibold text-brand-800 shadow-sm" : "hover:bg-cream-100 hover:text-brand-700"
                }`}
                href={href}
                key={item.label}
                title={item.label}
              >
                <Icon size={16} />
                <span className="hidden md:inline">{item.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="ml-auto inline-flex items-center justify-end">
          <div className="inline-flex items-center rounded-xl border border-cream-200 bg-cream-100/80 p-1 sm:p-1.5 shadow-sm">
            <button
              aria-expanded={paletteOpen}
              aria-label={paletteOpen ? "Thu gọn bảng màu" : "Mở bảng màu"}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-brand-800 transition hover:bg-cream-200 hover:text-brand-900 sm:h-8 sm:w-8"
              onClick={() => setPaletteOpen((open) => !open)}
              title={paletteOpen ? "Thu gọn bảng màu" : "Mở bảng màu"}
              type="button"
            >
              <Palette size={16} />
            </button>
            <div
              aria-hidden={!paletteOpen}
              className={`flex items-center gap-3 transition-all duration-300 ease-out ${
                paletteOpen
                  ? "ml-1.5 max-w-64 overflow-visible scale-100 opacity-100"
                  : "max-w-0 overflow-hidden scale-95 opacity-0 pointer-events-none"
              }`}
            >
              {themes.map((item) => (
                <button
                  aria-label={`Chọn màu ${item.label}`}
                  className={`h-6 w-6 rounded-full border transition hover:scale-105 ${theme === item.id ? "border-brand-800 ring-2 ring-brand-200" : "border-cream-300"}`}
                  key={item.id}
                  onClick={() => handleThemeChange(item.id)}
                  style={{ backgroundColor: item.color }}
                  title={item.label}
                  type="button"
                />
              ))}
            </div>
          </div>
        </div>
      </nav>
    </header>
  );
}

function applyTheme(themeId: string) {
  if (themeId === "sage") {
    document.documentElement.removeAttribute("data-theme");
    return;
  }
  document.documentElement.dataset.theme = themeId;
}

function subscribeTheme(callback: () => void) {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener("storage", callback);
  window.addEventListener(THEME_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(THEME_EVENT, callback);
  };
}

function getThemeSnapshot() {
  if (typeof window === "undefined") return "sage";
  return window.localStorage.getItem(THEME_KEY) ?? "sage";
}

function getServerThemeSnapshot() {
  return "sage";
}
