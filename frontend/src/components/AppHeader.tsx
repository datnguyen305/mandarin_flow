"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, KeyRound, Library, Palette, Home } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

const THEME_KEY = "fluentmandarin:pastel-theme";
const THEME_EVENT = "pastel-theme-updated";

const navItems = [
  { href: "/", label: "Trang chủ", icon: Home },
  { href: "/", label: "Video", icon: Library, watchOnly: true },
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
  const theme = useSyncExternalStore(subscribeTheme, getThemeSnapshot, getServerThemeSnapshot);

  useEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  function handleThemeChange(themeId: string) {
    window.localStorage.setItem(THEME_KEY, themeId);
    window.dispatchEvent(new CustomEvent(THEME_EVENT));
  }

  return (
    <header className="sticky top-0 z-30 border-b border-cream-200 bg-cream-50/90 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-700 font-serif text-lg font-bold text-cream-50 shadow-sm">
            汉
          </span>
          <span className="min-w-0">
            <span className="block truncate text-base font-bold leading-none text-brand-900">MandarinFlow</span>
            <span className="mt-1 block truncate text-xs font-medium text-slate-500">Học tiếng Trung qua video</span>
          </span>
        </Link>

        <div className="order-3 grid w-full grid-cols-3 gap-1 rounded-xl bg-cream-200/70 p-1 text-sm font-medium text-slate-600 sm:order-none sm:w-auto sm:flex sm:bg-transparent sm:p-0">
          {navItems.map((item) => {
            if (item.watchOnly && pathname !== "/watch") return null;
            const Icon = item.icon;
            const href = item.href;
            const active = item.watchOnly ? pathname === "/watch" : item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 transition ${
                  active ? "bg-cream-50 font-semibold text-brand-800 shadow-sm sm:border-b-2 sm:border-brand-700 sm:bg-transparent sm:pb-1 sm:shadow-none" : "hover:bg-cream-100 hover:text-brand-700 sm:hover:bg-transparent"
                }`}
                href={href}
                key={item.href}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="inline-flex items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-xl border border-cream-200 bg-cream-100/80 px-2.5 py-2 shadow-sm">
            <Palette size={16} className="text-brand-800" />
            <div className="flex items-center gap-1.5">
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
          <Link
            aria-label="Mở công cụ Dev"
            className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border shadow-sm transition ${
              pathname.startsWith("/dev")
                ? "border-brand-300 bg-brand-700 text-cream-50"
                : "border-cream-200 bg-cream-100/80 text-brand-800 hover:bg-cream-200"
            }`}
            href="/dev"
            title="Dev"
          >
            <KeyRound size={18} />
          </Link>
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
