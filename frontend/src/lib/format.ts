/**
 * The app's formatters. One place, so every surface prints money and dates the
 * same way (IA rule: every list is the same list).
 */

/** "CHF 1'949.45" — hand-rolled so node, Safari and Chrome agree on the apostrophe. */
export function formatCHF(amount: number | null | undefined, currency = "CHF"): string {
  if (amount == null || !Number.isFinite(amount)) return "–";
  const sign = amount < 0 ? "-" : "";
  const [int, frac] = Math.abs(amount).toFixed(2).split(".");
  return `${currency} ${sign}${int.replace(/\B(?=(\d{3})+(?!\d))/g, "'")}.${frac}`;
}

/** DD.MM.YYYY from an ISO date, "–" when unknown. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const [y, m, d] = iso.split("T")[0].split("-");
  return y && m && d ? `${d}.${m}.${y}` : iso;
}
