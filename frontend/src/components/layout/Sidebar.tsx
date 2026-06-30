"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { ChevronsLeft } from "lucide-react";
import { getNavSections, type NavItem } from "@/lib/navigation";
import { Logo } from "@/components/ui/Logo";
import { cn } from "@/lib/utils";

const sections = getNavSections();

function NavLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active =
    pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      className={cn(
        "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
        collapsed && "justify-center px-0",
        active ? "text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      {active && (
        <motion.span
          layoutId="sidebar-active"
          className="absolute inset-0 rounded-lg bg-primary shadow-sm shadow-primary/30"
          transition={{ type: "spring", bounce: 0.15, duration: 0.5 }}
        />
      )}
      <item.icon className={cn("relative z-10 h-[18px] w-[18px] shrink-0")} />
      {!collapsed && <span className="relative z-10 truncate">{item.label}</span>}
      {item.badge && !collapsed && (
        <span className="relative z-10 ml-auto rounded-full bg-brand-500/15 px-2 py-0.5 text-[10px] font-semibold text-brand-600 dark:text-brand-300">
          {item.badge}
        </span>
      )}
    </Link>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
  /** hide the collapse control (mobile drawer) */
  showCollapse?: boolean;
}

export function SidebarContent({ collapsed, onToggle, onNavigate, showCollapse = true }: SidebarProps) {
  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Header */}
      <div className={cn("flex h-[var(--topbar-height)] items-center border-b border-border px-4", collapsed && "justify-center px-0")}>
        <Logo collapsed={collapsed} />
        {showCollapse && !collapsed && (
          <button
            onClick={onToggle}
            aria-label="Seitenleiste einklappen"
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <ChevronsLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {Array.from(sections.entries()).map(([section, items]) => (
          <div key={section}>
            {!collapsed && (
              <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                {section}
              </p>
            )}
            <div className="space-y-1">
              {items.map((item) => (
                <NavLink key={item.href} item={item} collapsed={collapsed} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapsed expand control */}
      {showCollapse && collapsed && (
        <div className="border-t border-border p-3">
          <button
            onClick={onToggle}
            aria-label="Seitenleiste ausklappen"
            className="flex w-full items-center justify-center rounded-lg py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <ChevronsLeft className="h-4 w-4 rotate-180" />
          </button>
        </div>
      )}
    </div>
  );
}

/** Fixed desktop sidebar. */
export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 hidden border-r border-border transition-[width] duration-300 ease-out md:block",
        collapsed ? "w-[var(--sidebar-collapsed-width)]" : "w-[var(--sidebar-width)]"
      )}
    >
      <SidebarContent collapsed={collapsed} onToggle={onToggle} />
    </aside>
  );
}

/** Mobile slide-over drawer. */
export function MobileSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm md:hidden"
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 38 }}
            className="fixed inset-y-0 left-0 z-50 w-[var(--sidebar-width)] border-r border-border shadow-2xl md:hidden"
          >
            <SidebarContent collapsed={false} onToggle={() => {}} onNavigate={onClose} showCollapse={false} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
