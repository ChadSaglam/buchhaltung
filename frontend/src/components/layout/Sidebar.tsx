"use client";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useAuthStore } from "@/stores/auth-store";
import api from "@/lib/api";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  badge?: string;
}

interface SystemStatus {
  ollama: boolean;
  vision: boolean;
  visionModel: string;
  mlModel: boolean;
  mlAccuracy: number;
  memoryCount: number;
  bookingCount: number;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/dashboard/kontoauszug", label: "Kontoauszug", icon: "📄" },
  { href: "/dashboard/scanner", label: "Scanner", icon: "📸" },
  { href: "/dashboard/kontenplan", label: "Kontenplan", icon: "⚙️" },
  { href: "/dashboard/lernverlauf", label: "Lernverlauf", icon: "📈" },
  { href: "/dashboard/modell", label: "Modell", icon: "🧠" },
];

function StatusIndicator({ ok, pulse }: { ok: boolean; pulse?: boolean }) {
  return (
    <span className="relative flex h-2 w-2">
      {pulse && ok && (
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
      )}
      <span className={`relative inline-flex rounded-full h-2 w-2 ${ok ? "bg-emerald-500" : "bg-red-400"}`} />
    </span>
  );
}

function UserInitials({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  return (
    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-xs font-bold shadow-sm">
      {initials}
    </div>
  );
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const { user, logout } = useAuthStore();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    async function fetchStatus() {
      try {
        const [scannerRes, classifyRes, bookingsRes] = await Promise.allSettled([
          api.get("/api/scanner/status"),
          api.get("/api/classify/info"),
          api.get("/api/bookings/stats"),
        ]);
        if (!mounted) return;
        const scanner = scannerRes.status === "fulfilled" ? scannerRes.value.data : null;
        const classify = classifyRes.status === "fulfilled" ? classifyRes.value.data : null;
        const bookings = bookingsRes.status === "fulfilled" ? bookingsRes.value.data : null;
        setStatus({
          ollama: scanner?.ok ?? false,
          vision: (scanner?.vision_models?.length ?? 0) > 0,
          visionModel: scanner?.best_vision || scanner?.vision_models?.[0] || "",
          mlModel: classify?.has_model ?? false,
          mlAccuracy: classify?.model_accuracy ?? 0,
          memoryCount: classify?.memory_count ?? 0,
          bookingCount: bookings?.total_count ?? 0,
        });
      } catch {
        if (mounted) setStatus(null);
      }
    }
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  // Close user menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  if (isMobile) return null;

  const allOk = status ? status.ollama && status.vision && status.mlModel && status.memoryCount > 0 : false;

  const checklist = status ? [
    { label: "Ollama", ok: status.ollama, detail: status.ollama ? "Verbunden" : "Offline" },
    { label: "Vision", ok: status.vision, detail: status.visionModel || "Kein Modell" },
    { label: "ML-Modell", ok: status.mlModel, detail: status.mlModel ? `${Math.round(status.mlAccuracy * 100)}% Genauigkeit` : "Nicht trainiert" },
    { label: "Gedächtnis", ok: status.memoryCount > 0, detail: `${status.memoryCount} Einträge` },
    { label: "Buchungen", ok: status.bookingCount > 0, detail: `${status.bookingCount} gespeichert` },
  ] : [];

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 260 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="fixed left-0 top-0 h-screen z-40 flex flex-col bg-card/80 backdrop-blur-xl border-r border-border/50 shadow-[1px_0_12px_rgba(0,0,0,0.04)]"
    >
      {/* ── Logo ─────────────────────────────────────────── */}
      <div className="h-16 flex items-center px-5 gap-3 border-b border-border/50">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-sm shadow-brand-500/20">
          <span className="text-white text-sm">📒</span>
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="overflow-hidden"
            >
              <div className="font-bold text-foreground whitespace-nowrap text-sm">RDS Buchhaltung</div>
              <div className="text-[10px] text-muted-foreground whitespace-nowrap">Swiss Bookkeeping AI</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Navigation ───────────────────────────────────── */}
      <nav className="flex-1 py-3 px-2.5 space-y-0.5 overflow-y-auto">
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest px-3 pb-2 block"
            >
              Navigation
            </motion.span>
          )}
        </AnimatePresence>

        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <motion.div
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl relative transition-all duration-200 group ${
                  isActive
                    ? "bg-brand-600 text-white shadow-md shadow-brand-600/20"
                    : "text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                }`}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
              >
                <span className={`w-5 h-5 flex-shrink-0 text-center text-base transition-transform duration-200 ${
                  isActive ? "" : "group-hover:scale-110"
                }`}>
                  {item.icon}
                </span>
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="text-sm font-medium whitespace-nowrap"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {/* Tooltip for collapsed */}
                {collapsed && (
                  <div className="absolute left-full ml-3 px-2.5 py-1.5 bg-foreground text-background text-xs font-medium rounded-lg shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                    {item.label}
                  </div>
                )}
              </motion.div>
            </Link>
          );
        })}

        {/* ── System Status ──────────────────────────────── */}
        <AnimatePresence>
          {!collapsed && status && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="mt-5 mx-1 rounded-xl bg-muted/60 border border-border/50 p-3 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
                  System
                </span>
                <StatusIndicator ok={allOk} pulse />
              </div>
              <div className="space-y-1.5">
                {checklist.map((c) => (
                  <div key={c.label} className="flex items-center gap-2 group/item">
                    <StatusIndicator ok={c.ok} />
                    <span className="text-[11px] text-muted-foreground flex-1">{c.label}</span>
                    <span className={`text-[10px] font-mono truncate max-w-[90px] ${
                      c.ok ? "text-emerald-600" : "text-red-400"
                    }`}>
                      {c.detail}
                    </span>
                  </div>
                ))}
              </div>
              {!allOk && (
                <Link href="/dashboard/modell">
                  <div className="text-[10px] text-brand-600 hover:text-brand-700 font-medium cursor-pointer mt-1">
                    → Setup vervollständigen
                  </div>
                </Link>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapsed system indicator */}
        {collapsed && status && (
          <div className="flex justify-center pt-3">
            <div className="group relative">
              <StatusIndicator ok={allOk} pulse />
              <div className="absolute left-full ml-3 px-2.5 py-1.5 bg-foreground text-background text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                System: {allOk ? "✅ Alles OK" : "⚠️ Setup unvollständig"}
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* ── User Section ─────────────────────────────────── */}
      <div className="border-t border-border/50 relative" ref={userMenuRef}>
        {/* User menu popup */}
        <AnimatePresence>
          {userMenuOpen && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute bottom-full left-2 right-2 mb-2 bg-card rounded-xl border border-border shadow-xl shadow-black/10 overflow-hidden z-50"
            >
              <div className="p-3 border-b border-border/50 bg-muted/30">
                <div className="text-sm font-semibold text-foreground">{user?.display_name}</div>
                <div className="text-[11px] text-muted-foreground">{user?.email}</div>
                <div className="text-[10px] text-brand-600 font-medium mt-0.5">{user?.tenant_name} · {user?.role}</div>
              </div>
              <div className="py-1">
                <Link href="/dashboard/settings" onClick={() => setUserMenuOpen(false)}>
                  <div className="flex items-center gap-2.5 px-3 py-2 text-sm text-foreground hover:bg-muted/80 transition-colors cursor-pointer">
                    <span className="text-base">⚙️</span> Einstellungen
                  </div>
                </Link>
                <Link href="/dashboard/modell" onClick={() => setUserMenuOpen(false)}>
                  <div className="flex items-center gap-2.5 px-3 py-2 text-sm text-foreground hover:bg-muted/80 transition-colors cursor-pointer">
                    <span className="text-base">🧠</span> Modell verwalten
                  </div>
                </Link>
                <div className="border-t border-border/50 mt-1 pt-1">
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2.5 px-3 py-2 text-sm text-red-500 hover:bg-red-50 transition-colors cursor-pointer w-full text-left"
                  >
                    <span className="text-base">🚪</span> Abmelden
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* User button */}
        <button
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/60 transition-all duration-200 group"
        >
          {user ? (
            <UserInitials name={user.display_name} />
          ) : (
            <div className="w-8 h-8 rounded-lg bg-muted animate-pulse" />
          )}
          <AnimatePresence>
            {!collapsed && user && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 text-left min-w-0"
              >
                <div className="text-sm font-medium text-foreground truncate">{user.display_name}</div>
                <div className="text-[10px] text-muted-foreground truncate">{user.tenant_name}</div>
              </motion.div>
            )}
          </AnimatePresence>
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-muted-foreground group-hover:text-foreground transition-colors text-xs"
              >
                {userMenuOpen ? "▾" : "▸"}
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        {/* Collapse toggle */}
        <button
          onClick={() => { setCollapsed(!collapsed); setUserMenuOpen(false); }}
          className="w-full h-9 border-t border-border/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-all duration-200 group"
        >
          <motion.svg
            animate={{ rotate: collapsed ? 180 : 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            className="text-muted-foreground group-hover:text-brand-600 transition-colors"
          >
            <path
              d="M10 12L6 8L10 4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </motion.svg>
        </button>
      </div>
    </motion.aside>
  );
}
