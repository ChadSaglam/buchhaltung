"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { getActiveNavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";

/**
 * Breadcrumb trail derived from the current pathname. The dashboard root is the
 * "Home" crumb; the active nav item (resolved from ALL_NAV_ITEMS) is the leaf.
 * Kept compact so it sits inline in the Topbar.
 */
export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = usePathname();
  const active = getActiveNavItem(pathname);
  const isRoot = pathname === "/dashboard";

  return (
    <nav aria-label="Brotkrümel" className={cn("flex min-w-0 items-center gap-1.5 text-sm", className)}>
      <Link
        href="/dashboard"
        className={cn(
          "flex items-center gap-1.5 rounded-md px-1.5 py-1 transition-colors hover:bg-accent",
          isRoot ? "text-foreground" : "text-muted-foreground hover:text-foreground"
        )}
      >
        <Home className="h-3.5 w-3.5 shrink-0" />
        <span className="hidden sm:inline">Dashboard</span>
      </Link>

      {!isRoot && active && (
        <>
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
          <span className="flex min-w-0 items-center gap-1.5 font-semibold text-foreground">
            {active.icon && <active.icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
            <span className="truncate">{active.label}</span>
          </span>
        </>
      )}
    </nav>
  );
}
