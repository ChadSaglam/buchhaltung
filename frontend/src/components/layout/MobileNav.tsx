"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { useMediaQuery } from "@/hooks/useMediaQuery";

export function MobileNav() {
  const isMobile = useMediaQuery("(max-width: 768px)");
  const pathname = usePathname();

  if (!isMobile) return null;

  const items = [
    { href: "/dashboard", icon: "📊", label: "Home" },
    { href: "/dashboard/kontoauszug", icon: "📄", label: "Konto" },
    { href: "/dashboard/scanner", icon: "📸", label: "Scan" },
    { href: "/dashboard/kontenplan", icon: "⚙️", label: "Plan" },
    { href: "/dashboard/modell", icon: "🧠", label: "Modell" },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 h-16
      bg-card/80 backdrop-blur-xl border-t border-border
      flex items-center justify-around px-2 pb-[env(safe-area-inset-bottom)]"
    >
      {items.map((navItem) => {
        const isActive = pathname === navItem.href;
        return (
          <Link key={navItem.href} href={navItem.href} className="relative flex flex-col items-center gap-0.5 py-1 px-3">
            {isActive && (
              <motion.div
                layoutId="mobileActiveTab"
                className="absolute -top-px left-2 right-2 h-[2px] bg-brand-600 rounded-full"
              />
            )}
            <span className="text-lg">{navItem.icon}</span>
            <span className={`text-[10px] ${isActive ? "text-brand-600 font-medium" : "text-muted-foreground"}`}>
              {navItem.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
