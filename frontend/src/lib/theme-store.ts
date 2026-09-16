import { create } from "zustand";

export type Theme = "light" | "dark" | "system";
export type Accent = "blue" | "violet" | "emerald" | "amber" | "rose";

const THEME_KEY = "theme";
const ACCENT_KEY = "accent";

/**
 * Accent presets — primary/ring + the brand-300..700 ramp used across the UI.
 * "blue" is the platform brand: it sets nothing inline so the `--cd-*` tokens
 * in globals.css (light/dark aware) stay in charge; the values here are only
 * the swatch and a reference.
 */
export const ACCENTS: Record<Accent, { label: string; swatch: string; primary: string; ring: string; b400: string; b500: string; b600: string; b700: string; b300: string }> = {
  blue: { label: "Blau", swatch: "#2451e6", primary: "#2451e6", ring: "#3b6cf6", b300: "#8eb5ff", b400: "#598dff", b500: "#3b6cf6", b600: "#2451e6", b700: "#1d3fc4" },
  violet: { label: "Violett", swatch: "#7c3aed", primary: "#7c3aed", ring: "#8b5cf6", b300: "#c4b5fd", b400: "#a78bfa", b500: "#8b5cf6", b600: "#7c3aed", b700: "#6d28d9" },
  // B-58: the ramps are shifted one step darker. White on the old emerald was
  // 3.77:1 and on the old amber 3.19:1 — both below WCAG AA's 4.5:1 for the
  // primary button, and `text-brand-600` failed on a white card for the same
  // reason. See lib/theme-store.test.ts, which fails if any accent slips back.
  emerald: { label: "Smaragd", swatch: "#047857", primary: "#047857", ring: "#10b981", b300: "#6ee7b7", b400: "#10b981", b500: "#059669", b600: "#047857", b700: "#065f46" },
  amber: { label: "Bernstein", swatch: "#b45309", primary: "#b45309", ring: "#f59e0b", b300: "#fcd34d", b400: "#f59e0b", b500: "#d97706", b600: "#b45309", b700: "#92400e" },
  rose: { label: "Rosé", swatch: "#e11d48", primary: "#e11d48", ring: "#f43f5e", b300: "#fda4af", b400: "#fb7185", b500: "#f43f5e", b600: "#e11d48", b700: "#be123c" },
};

function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolve(theme: Theme): "light" | "dark" {
  return theme === "system" ? (systemPrefersDark() ? "dark" : "light") : theme;
}

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", resolve(theme) === "dark");
}

const ACCENT_VARS = ["--primary", "--ring", "--color-brand-300", "--color-brand-400", "--color-brand-500", "--color-brand-600", "--color-brand-700"];

function applyAccent(accent: Accent) {
  if (typeof document === "undefined") return;
  const root = document.documentElement.style;
  if (accent === "blue") {
    ACCENT_VARS.forEach((v) => root.removeProperty(v));
    return;
  }
  const a = ACCENTS[accent];
  root.setProperty("--primary", a.primary);
  root.setProperty("--ring", a.ring);
  root.setProperty("--color-brand-300", a.b300);
  root.setProperty("--color-brand-400", a.b400);
  root.setProperty("--color-brand-500", a.b500);
  root.setProperty("--color-brand-600", a.b600);
  root.setProperty("--color-brand-700", a.b700);
}

interface ThemeState {
  theme: Theme;
  resolved: "light" | "dark";
  accent: Accent;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
  setAccent: (accent: Accent) => void;
  hydrate: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: "system",
  resolved: "light",
  accent: "blue",
  setTheme: (theme) => {
    if (typeof window !== "undefined") localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    set({ theme, resolved: resolve(theme) });
  },
  toggle: () => {
    const next = get().resolved === "dark" ? "light" : "dark";
    get().setTheme(next);
  },
  setAccent: (accent) => {
    if (typeof window !== "undefined") localStorage.setItem(ACCENT_KEY, accent);
    applyAccent(accent);
    set({ accent });
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    const storedTheme = (localStorage.getItem(THEME_KEY) as Theme | null) ?? "system";
    const storedAccent = (localStorage.getItem(ACCENT_KEY) as Accent | null) ?? "blue";
    applyTheme(storedTheme);
    applyAccent(storedAccent);
    set({ theme: storedTheme, resolved: resolve(storedTheme), accent: storedAccent });

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", () => {
      if (get().theme === "system") {
        applyTheme("system");
        set({ resolved: resolve("system") });
      }
    });
  },
}));
