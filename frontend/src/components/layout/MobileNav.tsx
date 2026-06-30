"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { LayoutDashboard, FileText, ScanLine, ListChecks, Brain, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const items: { href: string; icon: LucideIcon; label: string }[] = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Home" },
  { href: "/dashboard/kontoauszug", icon: FileText, label: "Konto" },
  { href: "/dashboard/scanner", icon: ScanLine, label: "Scan" },
  { href: "/dashboard/review", icon: ListChecks, label: "Prüfen" },
  { href: "/dashboard/modell", icon: Brain, label: "Modell" },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="glass safe-area-inset-bottom fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t px-2 md:hidden">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="relative flex flex-1 flex-col items-center gap-0.5 py-1.5"
          >
            {active && (
              <motion.span
                layoutId="mobileActiveTab"
                className="absolute -top-px left-1/2 h-[3px] w-8 -translate-x-1/2 rounded-full bg-primary"
              />
            )}
            <item.icon className={cn("h-5 w-5 transition-colors", active ? "text-primary" : "text-muted-foreground")} />
            <span className={cn("text-[10px] font-medium transition-colors", active ? "text-primary" : "text-muted-foreground")}>
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
