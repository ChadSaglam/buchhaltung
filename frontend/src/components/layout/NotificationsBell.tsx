"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import { Bell, CheckCheck, ListChecks, Bot, Server, BookOpen, type LucideIcon } from "lucide-react";
import { useNotificationsStore, type NotifKind } from "@/lib/notifications-store";
import { cn } from "@/lib/utils";

const KIND_ICON: Record<NotifKind, LucideIcon> = {
  review: ListChecks,
  model: Bot,
  system: Server,
  booking: BookOpen,
};

const KIND_TINT: Record<NotifKind, string> = {
  review: "text-warning bg-warning/15",
  model: "text-brand-600 dark:text-brand-300 bg-brand-500/12",
  system: "text-destructive bg-destructive/10",
  booking: "text-success bg-success/12",
};

export function NotificationsBell() {
  const { items, loading, refresh, markRead, markAllRead, unreadCount } = useNotificationsStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const unread = unreadCount();

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 60_000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Benachrichtigungen"
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-50 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-border bg-card shadow-lg"
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <p className="text-sm font-semibold text-foreground">Benachrichtigungen</p>
              {items.length > 0 && (
                <button
                  onClick={markAllRead}
                  className="flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  <CheckCheck className="h-3.5 w-3.5" /> Alle gelesen
                </button>
              )}
            </div>

            <div className="max-h-[60vh] overflow-y-auto">
              {loading && items.length === 0 ? (
                <div className="space-y-3 p-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className="h-8 w-8 animate-pulse rounded-lg bg-muted" />
                      <div className="flex-1 space-y-2">
                        <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
                        <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : items.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                  Keine neuen Benachrichtigungen
                </div>
              ) : (
                <ul className="p-1.5">
                  {items.map((n) => {
                    const Icon = KIND_ICON[n.kind];
                    const inner = (
                      <div
                        className={cn(
                          "flex items-start gap-3 rounded-lg px-2.5 py-2.5 transition-colors hover:bg-accent",
                          !n.read && "bg-accent/50"
                        )}
                      >
                        <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", KIND_TINT[n.kind])}>
                          <Icon className="h-4 w-4" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                            <span className="truncate">{n.title}</span>
                            {!n.read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />}
                          </p>
                          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{n.body}</p>
                        </div>
                      </div>
                    );
                    return (
                      <li key={n.id}>
                        {n.href ? (
                          <Link href={n.href} onClick={() => { markRead(n.id); setOpen(false); }}>
                            {inner}
                          </Link>
                        ) : (
                          <button className="w-full text-left" onClick={() => markRead(n.id)}>
                            {inner}
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
