import { create } from "zustand";

/** Lightweight shared UI state for global overlays (assistant, shortcuts). */
interface UiState {
  assistantOpen: boolean;
  setAssistantOpen: (v: boolean) => void;
  toggleAssistant: () => void;

  shortcutsOpen: boolean;
  setShortcutsOpen: (v: boolean) => void;
  toggleShortcuts: () => void;
}

export const useUiStore = create<UiState>((set, get) => ({
  assistantOpen: false,
  setAssistantOpen: (v) => set({ assistantOpen: v }),
  toggleAssistant: () => set({ assistantOpen: !get().assistantOpen }),

  shortcutsOpen: false,
  setShortcutsOpen: (v) => set({ shortcutsOpen: v }),
  toggleShortcuts: () => set({ shortcutsOpen: !get().shortcutsOpen }),
}));
