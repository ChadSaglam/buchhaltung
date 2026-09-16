import { redirect } from "next/navigation";

/**
 * The *Belege* surface (`docs/IA-2026-09-14.md`). Its pages still live under
 * their old routes and are reachable as tabs, so this is the surface's address
 * and the list is its first tab.
 */
export default function BelegePage() {
  redirect("/dashboard/rechnungen");
}
