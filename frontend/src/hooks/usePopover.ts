"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";

/**
 * One popover behaviour for the whole app (B-58).
 *
 * Every dropdown in the topbar used to roll its own: some closed on an outside
 * click but not on Escape, some announced `aria-expanded` and some didn't, and
 * the listener stayed attached while the menu was shut. This hook gives the
 * trigger the ARIA a screen reader needs, closes on Escape and on an outside
 * click, and returns focus to the trigger when it closes with the keyboard.
 *
 *   const pop = usePopover();
 *   <div ref={pop.containerRef} className="relative">
 *     <button {...pop.triggerProps} ref={pop.triggerRef}>…</button>
 *     {pop.open && <div {...pop.popoverProps}>…</div>}
 *   </div>
 */
export function usePopover({ role = "menu" }: { role?: "menu" | "dialog" | "listbox" } = {}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const id = useId();

  const close = useCallback((focusTrigger = false) => {
    setOpen(false);
    if (focusTrigger) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      close(true);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

  return {
    open,
    setOpen,
    close,
    toggle: () => setOpen((o) => !o),
    containerRef,
    triggerRef,
    /** Spread onto the trigger `<button>`. */
    triggerProps: {
      type: "button" as const,
      "aria-haspopup": role,
      "aria-expanded": open,
      "aria-controls": open ? id : undefined,
      onClick: () => setOpen((o) => !o),
    },
    /** Spread onto the popover element. */
    popoverProps: { id, role },
  };
}
