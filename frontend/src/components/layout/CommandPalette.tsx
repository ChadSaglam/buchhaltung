"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import {
  Search, CornerDownLeft, ArrowUp, ArrowDown, Sun, Moon, Monitor,
  LogOut, Palette, Bot, Keyboard, type LucideIcon,
} from "lucide-react";
import { ALL_NAV_ITEMS } from "@/lib/navigation";
import { useCommandStore } from "@/lib/command-store";
import { useUiStore } from "@/lib/ui-store";
import { useThemeStore, ACCENTS, type Accent } from "@/lib/theme-store";
import { useAuthStore } from "@/lib/auth-store";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  hint?: string;
  group: string;
  icon: LucideIcon;
  keywords?: string;
  run: () => void;
  swatch?: string;
}

export function CommandPalette() {
  const { open, setOpen } = useCommandStore();
  const router = useRouter();
  const { setTheme, setAccent } = useThemeStore();
  const { logout } = useAuthStore();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [mounted, setMounted] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);

  // Global ⌘K / Ctrl+K to toggle, Esc handled in the dialog.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        useCommandStore.getState().toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const close = () => setOpen(false);
  const go = (href: string) => {
    router.push(href);
    close();
  };

  const commands = useMemo<Command[]>(() => {
    const nav: Command[] = ALL_NAV_ITEMS.map((item) => ({
      id: `nav-${item.href}`,
      label: item.label,
      hint: "Seite öffnen",
      group: "Navigation",
      icon: item.icon,
      keywords: item.section,
      run: () => go(item.href),
    }));

    const themes: Command[] = [
      { id: "theme-light", label: "Helles Design", group: "Design", icon: Sun, keywords: "hell light theme", run: () => { setTheme("light"); close(); } },
      { id: "theme-dark", label: "Dunkles Design", group: "Design", icon: Moon, keywords: "dunkel dark theme", run: () => { setTheme("dark"); close(); } },
      { id: "theme-system", label: "System-Design", group: "Design", icon: Monitor, keywords: "system auto theme", run: () => { setTheme("system"); close(); } },
    ];

    const accents: Command[] = (Object.keys(ACCENTS) as Accent[]).map((key) => ({
      id: `accent-${key}`,
      label: `Akzent: ${ACCENTS[key].label}`,
      group: "Design",
      icon: Palette,
      keywords: `akzent farbe accent color ${key}`,
      swatch: ACCENTS[key].swatch,
      run: () => { setAccent(key); close(); },
    }));

    const ui = useUiStore.getState();
    const actions: Command[] = [
      {
        id: "action-assistant",
        label: "AI-Assistent öffnen",
        group: "Aktionen",
        icon: Bot,
        keywords: "ai assistent chat frage hilfe",
        run: () => { ui.setAssistantOpen(true); close(); },
      },
      {
        id: "action-shortcuts",
        label: "Tastaturkürzel anzeigen",
        group: "Aktionen",
        icon: Keyboard,
        keywords: "shortcuts tastatur hilfe keyboard",
        run: () => { ui.setShortcutsOpen(true); close(); },
      },
      {
        id: "action-logout",
        label: "Abmelden",
        group: "Aktionen",
        icon: LogOut,
        keywords: "logout abmelden sign out",
        run: () => { logout(); router.replace("/login"); close(); },
      },
    ];

    return [...nav, ...themes, ...accents, ...actions];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) =>
      (c.label + " " + (c.keywords ?? "") + " " + c.group).toLowerCase().includes(q)
    );
  }, [query, commands]);

  // Group while preserving order.
  const groups = useMemo(() => {
    const map = new Map<string, Command[]>();
    filtered.forEach((c) => {
      if (!map.has(c.group)) map.set(c.group, []);
      map.get(c.group)!.push(c);
    });
    return Array.from(map.entries());
  }, [filtered]);

  // Flat list for keyboard index <-> command mapping.
  const flat = filtered;

  useEffect(() => {
    if (active >= flat.length) setActive(flat.length ? flat.length - 1 : 0);
  }, [flat.length, active]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % Math.max(flat.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i - 1 + Math.max(flat.length, 1)) % Math.max(flat.length, 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      flat[active]?.run();
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };

  // Scroll active item into view.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!mounted) return null;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-start justify-center p-4 pt-[12vh]"
        >
          <div className="absolute inset-0 bg-black/45 backdrop-blur-sm" onClick={close} />
          <motion.div
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            role="dialog"
            aria-modal="true"
            aria-label="Befehlspalette"
            className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          >
            {/* Search */}
            <div className="flex items-center gap-3 border-b border-border px-4">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
              <input
                autoFocus
                value={query}
                onChange={(e) => { setQuery(e.target.value); setActive(0); }}
                onKeyDown={onKeyDown}
                placeholder="Suchen oder Befehl eingeben…"
                className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
              <kbd className="hidden shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:block">
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[52vh] overflow-y-auto p-2">
              {flat.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                  Keine Ergebnisse für „{query}“
                </div>
              ) : (
                groups.map(([group, items]) => (
                  <div key={group} className="mb-1">
                    <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                      {group}
                    </p>
                    {items.map((cmd) => {
                      const idx = flat.indexOf(cmd);
                      const isActive = idx === active;
                      return (
                        <button
                          key={cmd.id}
                          data-idx={idx}
                          onMouseEnter={() => setActive(idx)}
                          onClick={() => cmd.run()}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                            isActive ? "bg-accent text-foreground" : "text-muted-foreground"
                          )}
                        >
                          {cmd.swatch ? (
                            <span className="h-[18px] w-[18px] shrink-0 rounded-full border border-black/10" style={{ backgroundColor: cmd.swatch }} />
                          ) : (
                            <cmd.icon className={cn("h-[18px] w-[18px] shrink-0", isActive ? "text-foreground" : "text-muted-foreground")} />
                          )}
                          <span className="flex-1 truncate text-foreground">{cmd.label}</span>
                          {cmd.hint && <span className="text-xs text-muted-foreground">{cmd.hint}</span>}
                          {isActive && <CornerDownLeft className="h-3.5 w-3.5 text-muted-foreground" />}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center gap-4 border-t border-border bg-muted/40 px-4 py-2 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1"><ArrowUp className="h-3 w-3" /><ArrowDown className="h-3 w-3" /> Navigieren</span>
              <span className="flex items-center gap-1"><CornerDownLeft className="h-3 w-3" /> Auswählen</span>
              <span className="ml-auto flex items-center gap-1">
                <kbd className="rounded border border-border bg-card px-1 py-0.5 font-medium">⌘</kbd>
                <kbd className="rounded border border-border bg-card px-1 py-0.5 font-medium">K</kbd>
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
