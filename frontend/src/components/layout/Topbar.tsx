"use client";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { getActiveNavItem } from "@/lib/navigation";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageSwitcher } from "@/components/ui/language_switcher";
import { UserMenu } from "@/components/layout/UserMenu";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const pathname = usePathname();
  const active = getActiveNavItem(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-[var(--topbar-height)] items-center gap-3 border-b border-border bg-surface/80 px-4 backdrop-blur-xl lg:px-6">
      <button
        onClick={onMenuClick}
        aria-label="Menü öffnen"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex items-center gap-2 min-w-0">
        {active?.icon && <active.icon className="hidden h-4 w-4 shrink-0 text-muted-foreground sm:block" />}
        <h2 className="truncate text-sm font-semibold text-foreground">{active?.label ?? "Dashboard"}</h2>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        <LanguageSwitcher className="hidden sm:flex" />
        <ThemeToggle />
        <div className="mx-1 hidden h-6 w-px bg-border sm:block" />
        <UserMenu />
      </div>
    </header>
  );
}
