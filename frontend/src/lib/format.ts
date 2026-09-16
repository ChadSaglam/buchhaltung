/**
 * The app's formatters. One place, so every surface prints money and dates the
 * same way (IA rule: every list is the same list).
 *
 * B-58: there used to be three. `scanner/helpers.ts` had its own `Intl`-based
 * `formatCHF` (which prints U+2019 ’ as the thousands mark, not the apostrophe
 * the rest of the app and the backend use) and `rechnungen/neu/helpers.ts` had
 * `chf()` for the bare number. Both now come from here.
 */

/** "1'949.45" — the bare amount, no currency. Hand-rolled so node, Safari and Chrome agree. */
export function formatAmount(amount: number | null | undefined): string {
  if (amount == null || !Number.isFinite(amount)) return "–";
  const sign = amount < 0 ? "-" : "";
  const [int, frac] = Math.abs(amount).toFixed(2).split(".");
  return `${sign}${int.replace(/\B(?=(\d{3})+(?!\d))/g, "'")}.${frac}`;
}

/** "CHF 1'949.45" — amounts are right-aligned wherever they sit in a column. */
export function formatCHF(amount: number | null | undefined, currency = "CHF"): string {
  const value = formatAmount(amount);
  return value === "–" ? value : `${currency} ${value}`;
}

/** DD.MM.YYYY from an ISO date, "–" when unknown. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const [y, m, d] = iso.split("T")[0].split("-");
  return y && m && d ? `${d}.${m}.${y}` : iso;
}
