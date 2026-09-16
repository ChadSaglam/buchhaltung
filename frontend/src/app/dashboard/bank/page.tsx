import { redirect } from "next/navigation";

/** The *Bank* surface — first tab is the Kontoauszug (`docs/IA-2026-09-14.md`). */
export default function BankPage() {
  redirect("/dashboard/kontoauszug");
}
