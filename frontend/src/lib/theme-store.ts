import { create } from "zustand";

export type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "theme";

function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolve(theme: Theme): "light" | "dark" {
  return theme === "system" ? (systemPrefersDark() ? "dark" : "light") : theme;
}

function apply(theme: Theme) {
  if (typeof document === "undefined") return;
  const resolved = resolve(theme);
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

interface ThemeState {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (theme: Theme) => void;
  toggle: () => void;
  hydrate: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: "system",
  resolved: "light",
  setTheme: (theme) => {
    if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, theme);
    apply(theme);
    set({ theme, resolved: resolve(theme) });
  },
  toggle: () => {
    const next = get().resolved === "dark" ? "light" : "dark";
    get().setTheme(next);
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
    apply(stored);
    set({ theme: stored, resolved: resolve(stored) });

    // React to OS changes while in "system" mode.
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", () => {
      if (get().theme === "system") {
        apply("system");
        set({ resolved: resolve("system") });
      }
    });
  },
}));
