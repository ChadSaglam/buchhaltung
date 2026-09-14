import { create } from "zustand";

/**
 * Notifications center.
 *
 * Events are synthesised from real system signals (review queue depth, model
 * training status, Ollama connectivity, recent bookings) so the bell reflects
 * things the user actually needs to act on — without requiring a dedicated
 * backend notifications table. Read state is persisted in localStorage so a
 * notification doesn't keep re-alerting after it's been seen.
 */
export type NotifKind = "review" | "model" | "system" | "booking";

export interface AppNotification {
  id: string;             // stable id so read-state persists
  kind: NotifKind;
  title: string;
  body: string;
  href?: string;
  ts: number;             // epoch ms (best-effort)
  read: boolean;
}

const READ_KEY = "notif-read-ids";

function loadReadIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    return new Set(JSON.parse(localStorage.getItem(READ_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function persistReadIds(ids: Set<string>) {
  if (typeof window === "undefined") return;
  localStorage.setItem(READ_KEY, JSON.stringify(Array.from(ids)));
}

export interface NotifSources {
  review: unknown;
  info: { has_model?: boolean; model_accuracy?: number } | null | undefined;
  aiStatus: { ok?: boolean } | null | undefined;
  stats: { total_count?: number; total_amount?: number } | null | undefined;
}

/** Pure: system signals → notification items (read flags applied by the store). */
export function buildNotifications({ review, info, aiStatus, stats }: NotifSources, now = Date.now()): AppNotification[] {
  const items: AppNotification[] = [];
  const reviewCount = Array.isArray(review) ? review.length : ((review as { count?: number } | null)?.count ?? 0);
  if (reviewCount > 0) {
    items.push({
      id: `review-${reviewCount}`,
      kind: "review",
      title: "Überprüfung ausstehend",
      body: `${reviewCount} Buchung${reviewCount === 1 ? "" : "en"} mit niedriger Konfidenz warten auf Bestätigung.`,
      href: "/dashboard/review",
      ts: now,
      read: false,
    });
  }

  if (info && info.has_model === false) {
    items.push({
      id: "model-untrained",
      kind: "model",
      title: "Modell noch nicht trainiert",
      body: "Trainiere das ML-Modell, um die automatische Kontierung zu verbessern.",
      href: "/dashboard/modell",
      ts: now,
      read: false,
    });
  } else if (info && typeof info.model_accuracy === "number" && info.model_accuracy > 0) {
    const pct = Math.round(info.model_accuracy * 100);
    items.push({
      id: `model-acc-${pct}`,
      kind: "model",
      title: "Modell aktiv",
      body: `Aktuelle Genauigkeit: ${pct}%.`,
      href: "/dashboard/modell",
      ts: now,
      read: false,
    });
  }

  if (aiStatus && aiStatus.ok === false) {
    items.push({
      id: "ollama-offline",
      kind: "system",
      title: "Ollama nicht erreichbar",
      body: "Der lokale AI-Dienst ist offline. Scanner und Assistent sind eingeschränkt.",
      href: "/dashboard/scanner",
      ts: now,
      read: false,
    });
  }

  if (stats && (stats.total_count ?? 0) > 0) {
    items.push({
      id: `bookings-${stats.total_count}`,
      kind: "booking",
      title: "Buchungen gespeichert",
      body: `${stats.total_count} Buchungen in der Datenbank (Total CHF ${Number(stats.total_amount ?? 0).toFixed(2)}).`,
      href: "/dashboard/kontoauszug",
      ts: now,
      read: false,
    });
  }
  return items;
}

interface NotifState {
  items: AppNotification[];
  /** Feed the store from the shared SWR readers (B-16) — no fetch of its own. */
  setFromSources: (sources: NotifSources) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  unreadCount: () => number;
  /** Drop everything in memory (logout). Read-ids in localStorage stay — they are harmless per browser. */
  reset: () => void;
}

export const useNotificationsStore = create<NotifState>((set, get) => ({
  items: [],
  setFromSources: (sources) => {
    const readIds = loadReadIds();
    const items = buildNotifications(sources).map((it) => ({ ...it, read: readIds.has(it.id) }));
    const prev = get().items;
    // Same ids, same read flags → keep the reference so subscribers don't re-render every poll.
    if (prev.length === items.length && prev.every((p, i) => p.id === items[i].id && p.read === items[i].read)) return;
    set({ items });
  },
  markRead: (id) => {
    const readIds = loadReadIds();
    readIds.add(id);
    persistReadIds(readIds);
    set({ items: get().items.map((i) => (i.id === id ? { ...i, read: true } : i)) });
  },
  markAllRead: () => {
    const readIds = loadReadIds();
    get().items.forEach((i) => readIds.add(i.id));
    persistReadIds(readIds);
    set({ items: get().items.map((i) => ({ ...i, read: true })) });
  },
  unreadCount: () => get().items.filter((i) => !i.read).length,
  reset: () => set({ items: [] }),
}));
