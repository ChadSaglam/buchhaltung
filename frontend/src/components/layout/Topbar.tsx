"use client";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Menu, Search, PanelLeftClose, PanelLeftOpen, HelpCircle, Bot } from "lucide-react";
import { useCommandStore } from "@/lib/command-store";
import { useUiStore } from "@/lib/ui-store";
import { getQuickActions } from "@/lib/quick-actions";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageSwitcher } from "@/components/ui/language_switcher";
import { UserMenu } from "@/components/layout/UserMenu";
import { NotificationsBell } from "@/components/layout/NotificationsBell";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

interface TopbarProps {
  onMenuClick: () => void;
  onToggleSidebar: () => void;
  sidebarCollapsed: boolean;
}

export function Topbar({ onMenuClick, onToggleSidebar, sidebarCollapsed }: TopbarProps) {
  const pathname = usePathname();
  const openCommand = useCommandStore((s) => s.setOpen);
  const { toggleAssistant, toggleShortcuts } = useUiStore();
  const quickActions = getQuickActions(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-[var(--topbar-height)] items-center gap-2 border-b border-border bg-surface/80 px-4 backdrop-blur-xl lg:px-6">
      {/* Mobile menu */}
      <button
        onClick={onMenuClick}
        aria-label="Menü öffnen"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Desktop sidebar toggle — bidirectional */}
      <button
        onClick={onToggleSidebar}
        aria-label={sidebarCollapsed ? "Seitenleiste ausklappen" : "Seitenleiste einklappen"}
        aria-expanded={!sidebarCollapsed}
        title={sidebarCollapsed ? "Seitenleiste ausklappen" : "Seitenleiste einklappen"}
        className="hidden h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:flex"
      >
        {sidebarCollapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
      </button>

      {/* Breadcrumbs */}
      <Breadcrumbs className="min-w-0" />

      {/* Per-page quick actions */}
      {quickActions.length > 0 && (
        <div className="ml-2 hidden items-center gap-1.5 border-l border-border pl-3 xl:flex">
          {quickActions.map((a) => (
            <Link
              key={a.href + a.label}
              href={a.href}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              <a.icon className="h-3.5 w-3.5" />
              {a.label}
            </Link>
          ))}
        </div>
      )}

      {/* Command palette trigger */}
      <button
        onClick={() => openCommand(true)}
        className="ml-3 hidden h-9 max-w-xs flex-1 items-center gap-2 rounded-lg border border-border bg-muted/60 px-3 text-sm text-muted-foreground transition-colors hover:border-border-strong hover:bg-muted lg:flex"
      >
        <Search className="h-4 w-4" />
        <span>Suchen…</span>
        <span className="ml-auto flex items-center gap-0.5">
          <kbd className="rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-medium">⌘</kbd>
          <kbd className="rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-medium">K</kbd>
        </span>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Mobile command trigger */}
        <button
          onClick={() => openCommand(true)}
          aria-label="Befehlspalette öffnen"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
        >
          <Search className="h-[18px] w-[18px]" />
        </button>

        {/* AI assistant */}
        <button
          onClick={toggleAssistant}
          aria-label="AI-Assistent öffnen"
          title="AI-Assistent (A)"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Bot className="h-[18px] w-[18px]" />
        </button>

        <NotificationsBell />

        {/* Keyboard shortcuts help */}
        <button
          onClick={toggleShortcuts}
          aria-label="Tastaturkürzel anzeigen"
          title="Tastaturkürzel (?)"
          className="hidden h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:flex"
        >
          <HelpCircle className="h-[18px] w-[18px]" />
        </button>

        <LanguageSwitcher className="hidden sm:flex" />
        <ThemeToggle />
        <div className="mx-1 hidden h-6 w-px bg-border sm:block" />
        <UserMenu />
      </div>
    </header>
  );
}
