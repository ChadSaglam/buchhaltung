"use client";
import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal behaviour for a custom dialog or drawer (B-19):
 *  - moves focus into the container when it opens (first focusable, else the
 *    container itself), unless something inside already has focus
 *    (`autoFocus` inputs);
 *  - keeps Tab / Shift+Tab cycling inside;
 *  - Escape calls `onClose`;
 *  - restores focus to the element that opened it when it closes.
 *
 * The container ref must point at the dialog element; give it
 * `tabIndex={-1}` so it can take focus when it has no focusable children.
 */
export function useFocusTrap(open: boolean, onClose: () => void, container: RefObject<HTMLElement | null>) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;

    const focusables = () =>
      Array.from(container.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );

    // Animated dialogs mount their content a frame after `open` flips.
    const raf = requestAnimationFrame(() => {
      const el = container.current;
      if (!el || el.contains(document.activeElement)) return;
      (focusables()[0] ?? el).focus();
    });

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
        return;
      }
      if (e.key !== "Tab" || !container.current) return;
      const items = focusables();
      if (items.length === 0) {
        e.preventDefault();
        container.current.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !container.current.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !container.current.contains(active))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("keydown", onKey);
      if (previous && document.contains(previous)) previous.focus();
    };
  }, [open, container]);
}
