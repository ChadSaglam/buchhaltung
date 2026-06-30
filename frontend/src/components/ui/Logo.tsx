import { cn } from "@/lib/utils";

/**
 * Buchhaltung brand mark — a stacked "ledger" glyph: two offset rounded
 * bars forming a "B" suggestion, drawn with currentColor so it adapts to theme.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={cn("h-full w-full", className)}
    >
      <rect width="32" height="32" rx="9" className="fill-primary" />
      <path
        d="M11 9.5h7.2c2.2 0 3.8 1.4 3.8 3.4 0 1.4-.8 2.5-2 3 1.5.4 2.5 1.6 2.5 3.2 0 2.2-1.7 3.6-4.1 3.6H11V9.5Z"
        fill="white"
        fillOpacity="0.0"
      />
      <path
        d="M11.5 9.5v13M11.5 9.5h6.6c1.9 0 3.2 1.2 3.2 2.9s-1.3 2.9-3.2 2.9h-6.6m0 0h7.1c2 0 3.4 1.2 3.4 3s-1.4 3.2-3.4 3.2h-7.1"
        stroke="white"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-9 w-9 shrink-0">
        <LogoMark />
      </div>
      {!collapsed && (
        <div className="leading-tight">
          <p className="text-sm font-bold tracking-tight text-foreground">Buchhaltung</p>
          <p className="text-[11px] font-medium text-muted-foreground">Swiss Bookkeeping</p>
        </div>
      )}
    </div>
  );
}
