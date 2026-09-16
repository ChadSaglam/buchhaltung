"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, LogOut, Settings, User as UserIcon } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { usePopover } from "@/hooks/usePopover";
import { cn } from "@/lib/utils";

function initials(name?: string, email?: string) {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

export function UserMenu() {
  const router = useRouter();
  const { user, hydrate, logout } = useAuthStore();
  const pop = usePopover();
  const { open, close, containerRef, triggerRef, triggerProps, popoverProps } = pop;

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        {...triggerProps}
        aria-label="Kontomenü"
        className="flex cursor-pointer items-center gap-2 rounded-lg p-1 pr-2 text-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
          {initials(user?.display_name, user?.email)}
        </span>
        <span className="hidden max-w-[120px] truncate text-left md:block">
          <span className="block text-xs font-semibold leading-tight text-foreground">
            {user?.display_name || "Konto"}
          </span>
          <span className="block truncate text-[11px] leading-tight text-muted-foreground">
            {user?.tenant_name || user?.email}
          </span>
        </span>
        <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            {...popoverProps}
            aria-label="Kontomenü"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-xl border border-border bg-card shadow-lg"
          >
            <div className="border-b border-border px-4 py-3">
              <p className="truncate text-sm font-semibold text-foreground">{user?.display_name || "Konto"}</p>
              <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
            </div>
            <div className="p-1.5">
              <Link
                href="/dashboard/settings"
                role="menuitem"
                onClick={() => close()}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent"
              >
                <UserIcon className="h-4 w-4 text-muted-foreground" /> Profil
              </Link>
              <Link
                href="/dashboard/settings"
                role="menuitem"
                onClick={() => close()}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent"
              >
                <Settings className="h-4 w-4 text-muted-foreground" /> Einstellungen
              </Link>
            </div>
            <div className="border-t border-border p-1.5">
              <button
                type="button"
                role="menuitem"
                onClick={handleLogout}
                className="flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-destructive transition-colors hover:bg-destructive/10"
              >
                <LogOut className="h-4 w-4" /> Abmelden
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
