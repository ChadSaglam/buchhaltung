import { create } from "zustand";
import api from "@/lib/api";

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

interface NotifState {
  items: AppNotification[];
  loading: boolean;
  refresh: () => Promise<void>;
  markRead: (id: string) => void;
  markAllRead: () => void;
  unreadCount: () => number;
}

export const useNotificationsStore = create<NotifState>((set, get) => ({
  items: [],
  loading: false,
  refresh: async () => {
    set({ loading: true });
    const readIds = loadReadIds();
    const items: AppNotification[] = [];
    const now = Date.now();

    const [review, info, aiStatus, stats] = await Promise.all([
      api.get("/api/review/").then((r) => r.data).catch(() => []),
      api.get("/api/classify/info").then((r) => r.data).catch(() => null),
      api.get("/api/ai/status").then((r) => r.data).catch(() => null),
      api.get("/api/bookings/stats").then((r) => r.data).catch(() => null),
    ]);

    const reviewCount = Array.isArray(review) ? review.length : (review?.count ?? 0);
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

    for (const it of items) it.read = readIds.has(it.id);
    set({ items, loading: false });
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
}));
