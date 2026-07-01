"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { Sidebar, MobileSidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { MobileNav } from "@/components/layout/MobileNav";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { ShortcutsModal } from "@/components/layout/ShortcutsModal";
import { AssistantPanel } from "@/components/layout/AssistantPanel";
import { useSidebarStore } from "@/lib/sidebar-store";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { collapsed, toggle, hydrate } = useSidebarStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  // Hydrate persisted collapse state, then clear the no-flash marker.
  useEffect(() => {
    hydrate();
    document.documentElement.classList.remove("sidebar-collapsed");
  }, [hydrate]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div
        data-sidebar-main
        className={cn(
          "flex min-h-screen flex-col transition-[margin] duration-300 ease-out",
          collapsed ? "md:ml-[var(--sidebar-collapsed-width)]" : "md:ml-[var(--sidebar-width)]"
        )}
      >
        <Topbar onMenuClick={() => setMobileOpen(true)} onToggleSidebar={toggle} sidebarCollapsed={collapsed} />

        <main className="flex-1 px-4 pb-24 pt-6 md:pb-8 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <AnimatePresence mode="wait">
              <motion.div
                key={pathname}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                {children}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>

      <MobileNav />
      <CommandPalette />
      <ShortcutsModal />
      <AssistantPanel />
    </div>
  );
}
