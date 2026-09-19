"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { SURFACES, surfaceFor } from "@/lib/navigation";

/** The same four surfaces as the sidebar — one bar, one mental model. */
const items = SURFACES;

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Hauptnavigation (mobil)" className="glass safe-area-inset-bottom fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t px-2 md:hidden">
      {items.map((item) => {
        const active = surfaceFor(pathname)?.href === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className="relative flex flex-1 flex-col items-center gap-0.5 py-1.5"
          >
            {active && (
              <motion.span
                layoutId="mobileActiveTab"
                className="absolute -top-px left-1/2 h-[3px] w-8 -translate-x-1/2 rounded-full bg-primary"
              />
            )}
            <item.icon className={cn("h-5 w-5 transition-colors", active ? "text-link" : "text-muted-foreground")} aria-hidden="true" />
            <span className={cn("text-[10px] font-medium transition-colors", active ? "text-link" : "text-muted-foreground")}>
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
