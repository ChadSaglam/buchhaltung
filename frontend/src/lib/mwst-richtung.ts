/**
 * B-93: the minus on `V81 / -8.10` is a convention, not a defect — and it reached
 * the screen with no explanation.
 *
 * `classifier.py` states it: *"a negative rate (Umsatzsteuer) flips the sign"*.
 * Negative means VAT we owe on our own revenue (Umsatzsteuer); positive means VAT
 * we paid a supplier and can reclaim (Vorsteuer). The VAT return computes
 * correctly from it. What the user saw was a rate that appeared to be below zero.
 *
 * So: show the number without its sign, and say which direction it runs. One
 * place, because the rate is rendered on the Bank table, the scanner card and the
 * Beleg — the recurring "two places, one truth" family (B-83, B-85, B-86, B-87,
 * B-90, B-92) is exactly what this file exists to avoid.
 */

export type MwstRichtung = "umsatz" | "vorsteuer" | "keine";

export function mwstRichtung(pct: string | number | null | undefined): MwstRichtung {
  const n = typeof pct === "number" ? pct : parseFloat(String(pct ?? "").replace(",", "."));
  if (!Number.isFinite(n) || n === 0) return "keine";
  return n < 0 ? "umsatz" : "vorsteuer";
}

/** The rate as a person reads it: `-8.10` → `8.10 %`. */
export function mwstSatzLabel(pct: string | number | null | undefined): string {
  const n = typeof pct === "number" ? pct : parseFloat(String(pct ?? "").replace(",", "."));
  if (!Number.isFinite(n) || n === 0) return "";
  return `${Math.abs(n).toFixed(2)} %`;
}

/** Short direction label for the cell next to the rate. */
export function mwstRichtungLabel(pct: string | number | null | undefined): string {
  switch (mwstRichtung(pct)) {
    case "umsatz":
      return "geschuldet";
    case "vorsteuer":
      return "Vorsteuer";
    default:
      return "";
  }
}

/** The full sentence, for a tooltip. */
export function mwstRichtungErklaerung(pct: string | number | null | undefined): string {
  switch (mwstRichtung(pct)) {
    case "umsatz":
      return "Umsatzsteuer: MwSt auf unserem eigenen Umsatz — die schulden wir der ESTV. Intern mit Minus geführt, damit die Abrechnung die Richtung kennt.";
    case "vorsteuer":
      return "Vorsteuer: MwSt, die wir einem Lieferanten bezahlt haben — die holen wir zurück.";
    default:
      return "";
  }
}
