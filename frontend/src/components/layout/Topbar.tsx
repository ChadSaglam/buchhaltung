"use client";
import { usePathname } from "next/navigation";
import { Menu, Search } from "lucide-react";
import { getActiveNavItem } from "@/lib/navigation";
import { useCommandStore } from "@/lib/command-store";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageSwitcher } from "@/components/ui/language_switcher";
import { UserMenu } from "@/components/layout/UserMenu";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const pathname = usePathname();
  const active = getActiveNavItem(pathname);
  const openCommand = useCommandStore((s) => s.setOpen);

  return (
    <header className="sticky top-0 z-30 flex h-[var(--topbar-height)] items-center gap-3 border-b border-border bg-surface/80 px-4 backdrop-blur-xl lg:px-6">
      <button
        onClick={onMenuClick}
        aria-label="Menü öffnen"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex min-w-0 items-center gap-2">
        {active?.icon && <active.icon className="hidden h-4 w-4 shrink-0 text-muted-foreground sm:block" />}
        <h2 className="truncate text-sm font-semibold text-foreground">{active?.label ?? "Dashboard"}</h2>
      </div>

      {/* Command palette trigger */}
      <button
        onClick={() => openCommand(true)}
        className="ml-4 hidden h-9 max-w-xs flex-1 items-center gap-2 rounded-lg border border-border bg-muted/60 px-3 text-sm text-muted-foreground transition-colors hover:border-border-strong hover:bg-muted lg:flex"
      >
        <Search className="h-4 w-4" />
        <span>Suchen…</span>
        <span className="ml-auto flex items-center gap-0.5">
          <kbd className="rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-medium">⌘</kbd>
          <kbd className="rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-medium">K</kbd>
        </span>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        <button
          onClick={() => openCommand(true)}
          aria-label="Befehlspalette öffnen"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
        >
          <Search className="h-[18px] w-[18px]" />
        </button>
        <LanguageSwitcher className="hidden sm:flex" />
        <ThemeToggle />
        <div className="mx-1 hidden h-6 w-px bg-border sm:block" />
        <UserMenu />
      </div>
    </header>
  );
}
