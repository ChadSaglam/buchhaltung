import { create } from "zustand";

/**
 * Sidebar collapse state, persisted to localStorage.
 *
 * The desktop sidebar can be collapsed to an icon rail and expanded back. The
 * choice is remembered across reloads. Hydration reads localStorage once on
 * mount; a no-flash class on <html> (set by SidebarScript) keeps the very first
 * paint correct so the rail doesn't flash open → closed.
 */
const KEY = "sidebar-collapsed";

interface SidebarState {
  collapsed: boolean;
  hydrated: boolean;
  setCollapsed: (v: boolean) => void;
  toggle: () => void;
  hydrate: () => void;
}

export const useSidebarStore = create<SidebarState>((set, get) => ({
  collapsed: false,
  hydrated: false,
  setCollapsed: (v) => {
    if (typeof window !== "undefined") localStorage.setItem(KEY, String(v));
    set({ collapsed: v });
  },
  toggle: () => get().setCollapsed(!get().collapsed),
  hydrate: () => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(KEY) === "true";
    set({ collapsed: stored, hydrated: true });
  },
}));
