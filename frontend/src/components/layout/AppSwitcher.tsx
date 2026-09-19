"use client";
import { AnimatePresence, motion } from "motion/react";
import { ExternalLink, LayoutGrid, Receipt } from "lucide-react";
import { BILLING_URL } from "@/lib/platform";
import { t } from "@/lib/i18n";
import { usePopover } from "@/hooks/usePopover";

/**
 * "Apps" menu (chadev-platform/contracts/sso.md, app switcher). Billing is
 * the identity issuer, so the entry is a plain link — its session is already
 * in the browser when the user arrived via SSO. Renders nothing while
 * `NEXT_PUBLIC_BILLING_URL` is unset: no entry, no dead link.
 */
export function AppSwitcher() {
  const { open, close, containerRef, triggerRef, triggerProps, popoverProps } = usePopover();

  if (!BILLING_URL) return null;

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        {...triggerProps}
        aria-label={t("apps.open")}
        title={t("apps.label")}
        className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <LayoutGrid className="h-[18px] w-[18px]" aria-hidden="true" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            {...popoverProps}
            aria-label={t("apps.label")}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-card p-1.5 shadow-lg"
          >
            <a
              role="menuitem"
              href={BILLING_URL}
              onClick={() => close()}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Receipt className="h-4 w-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold leading-tight">{t("apps.billing")}</span>
                <span className="block truncate text-[11px] leading-tight text-muted-foreground">
                  {t("apps.billing_desc")}
                </span>
              </span>
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            </a>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
