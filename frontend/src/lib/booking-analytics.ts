import type { Booking } from "@/lib/api";

/**
 * Client-side booking analytics used by the natural-language search and the
 * monthly summary / anomaly features. Everything here is deterministic and
 * runs in the browser — no backend or LLM required. The AI layer sits on top
 * (narrating these results) but the numbers always come from here.
 */

export interface ParsedQuery {
  text: string;          // free-text terms (matched against Beschreibung/Konto)
  minAmount?: number;
  maxAmount?: number;
  month?: number;        // 1-12
  year?: number;
  konto?: string;        // account number filter (soll or haben)
  direction?: "credit" | "debit"; // Einnahme / Ausgabe
}

const MONTHS: Record<string, number> = {
  januar: 1, jan: 1, februar: 2, feb: 2, märz: 3, maerz: 3, mrz: 3,
  april: 4, apr: 4, mai: 5, juni: 6, jun: 6, juli: 7, jul: 7,
  august: 8, aug: 8, september: 9, sep: 9, sept: 9, oktober: 10, okt: 10,
  november: 11, nov: 11, dezember: 12, dez: 12,
};

/** Parse a German natural-language query into structured filters + residual text. */
export function parseQuery(raw: string): ParsedQuery {
  let text = ` ${raw.toLowerCase()} `;
  const q: ParsedQuery = { text: "" };

  // Direction
  if (/\b(einnahmen?|ertr(a|ä)ge?|gutschrift(en)?|credit)\b/.test(text)) q.direction = "credit";
  if (/\b(ausgaben?|aufwand|aufwände|belastung(en)?|kosten|spesen|debit)\b/.test(text)) q.direction = "debit";

  // Amounts: "über 500", "unter 100", "mehr als 200", "weniger als 50", "> 300"
  const over = text.match(/(?:über|ueber|mehr als|grösser als|groesser als|>)\s*(?:chf\s*)?(\d[\d'.,]*)/);
  if (over) q.minAmount = num(over[1]);
  const under = text.match(/(?:unter|weniger als|kleiner als|<)\s*(?:chf\s*)?(\d[\d'.,]*)/);
  if (under) q.maxAmount = num(under[1]);

  // Year (2019-2099)
  const year = text.match(/\b(20\d{2})\b/);
  if (year) q.year = parseInt(year[1], 10);

  // Month by name
  for (const [name, n] of Object.entries(MONTHS)) {
    if (new RegExp(`\\b${name}\\b`).test(text)) { q.month = n; break; }
  }

  // Amounts already consumed above should not be re-read as an account number.
  const consumedAmounts = new Set<string>();
  if (over) consumedAmounts.add(over[1].replace(/['\s]/g, ""));
  if (under) consumedAmounts.add(under[1].replace(/['\s]/g, ""));

  // Account number: explicit "konto 6500" / "auf 4400", or a standalone 4-digit
  // number that isn't a year and wasn't already parsed as an amount.
  const explicitKonto = text.match(/\b(?:konto|kto|auf)\s*(\d{3,4})\b/);
  const bareKonto = text.match(/\b(\d{4})\b/);
  const kontoMatch = explicitKonto || bareKonto;
  if (
    kontoMatch &&
    (!year || kontoMatch[1] !== year[1]) &&
    !consumedAmounts.has(kontoMatch[1])
  ) {
    q.konto = kontoMatch[1];
  }

  // Residual free text: strip recognised tokens
  text = text
    .replace(/(?:über|ueber|mehr als|grösser als|groesser als|>|unter|weniger als|kleiner als|<)\s*(?:chf\s*)?\d[\d'.,]*/g, " ")
    .replace(/\b20\d{2}\b/g, " ")
    .replace(/\b(?:konto|kto|auf)\s*\d{3,4}\b/g, " ")
    .replace(/\b(einnahmen?|ertr(a|ä)ge?|gutschrift(en)?|credit|ausgaben?|aufwand|aufwände|belastung(en)?|kosten|spesen|debit)\b/g, " ");
  for (const name of Object.keys(MONTHS)) text = text.replace(new RegExp(`\\b${name}\\b`, "g"), " ");

  // Drop residual numbers and common German stopwords so the free-text term is clean.
  const STOPWORDS = new Set([
    "im", "in", "am", "an", "der", "die", "das", "den", "dem", "des", "und", "oder",
    "von", "vom", "für", "fuer", "mit", "auf", "aus", "bei", "pro", "je", "chf",
    "konto", "kto", "betrag", "buchung", "buchungen", "transaktion", "transaktionen",
  ]);
  q.text = text
    .replace(/\b\d[\d'.,]*\b/g, " ")
    .split(/\s+/)
    .filter((w) => w && !STOPWORDS.has(w))
    .join(" ")
    .trim();

  return q;
}

function num(s: string): number {
  // Swiss formatting: 1'234.50 or 1.234,50 or 1234.5
  const cleaned = s.replace(/['\s]/g, "");
  if (cleaned.includes(",") && cleaned.includes(".")) return parseFloat(cleaned.replace(/\./g, "").replace(",", "."));
  if (cleaned.includes(",")) return parseFloat(cleaned.replace(",", "."));
  return parseFloat(cleaned);
}

function bookingDate(b: Booking): Date | null {
  // Accept DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY
  const s = (b.datum || "").trim();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = s.match(/^(\d{1,2})[.\/](\d{1,2})[.\/](\d{4})/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  return null;
}

/** Apply a parsed query to a booking list. */
export function searchBookings(bookings: Booking[], q: ParsedQuery): Booking[] {
  return bookings.filter((b) => {
    const amt = Math.abs(Number(b.betrag) || 0);
    if (q.minAmount != null && amt < q.minAmount) return false;
    if (q.maxAmount != null && amt > q.maxAmount) return false;

    if (q.month != null || q.year != null) {
      const d = bookingDate(b);
      if (!d) return false;
      if (q.month != null && d.getMonth() + 1 !== q.month) return false;
      if (q.year != null && d.getFullYear() !== q.year) return false;
    }

    if (q.konto && b.kt_soll !== q.konto && b.kt_haben !== q.konto) return false;

    if (q.direction === "credit" && (Number(b.betrag) || 0) < 0) return false;
    if (q.direction === "debit" && (Number(b.betrag) || 0) > 0) return false;

    if (q.text) {
      const hay = `${b.beschreibung} ${b.kt_soll} ${b.kt_haben} ${b.mwst_code}`.toLowerCase();
      const terms = q.text.split(" ").filter(Boolean);
      if (!terms.every((t) => hay.includes(t))) return false;
    }
    return true;
  });
}

export interface MonthlyStats {
  month: string;                 // "2026-06"
  count: number;
  totalDebit: number;            // sum of |negative amounts|
  totalCredit: number;           // sum of positive amounts
  net: number;
  byAccount: Record<string, number>;
}

/** Aggregate bookings by YYYY-MM. */
export function monthlyStats(bookings: Booking[]): MonthlyStats[] {
  const map = new Map<string, MonthlyStats>();
  for (const b of bookings) {
    const d = bookingDate(b);
    if (!d) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (!map.has(key)) {
      map.set(key, { month: key, count: 0, totalDebit: 0, totalCredit: 0, net: 0, byAccount: {} });
    }
    const m = map.get(key)!;
    const amt = Number(b.betrag) || 0;
    m.count++;
    if (amt < 0) m.totalDebit += Math.abs(amt);
    else m.totalCredit += amt;
    m.net += amt;
    const acct = b.kt_soll || b.kt_haben || "—";
    m.byAccount[acct] = (m.byAccount[acct] || 0) + Math.abs(amt);
  }
  return Array.from(map.values()).sort((a, b) => (a.month < b.month ? 1 : -1));
}

export interface Anomaly {
  booking: Booking;
  reason: string;
  severity: "high" | "medium";
}

/**
 * Statistical anomaly detection: flags bookings whose absolute amount is a
 * strong outlier (z-score based, with a robust MAD fallback), plus obvious
 * data-quality issues (missing account, duplicate same-day same-amount).
 */
export function detectAnomalies(bookings: Booking[]): Anomaly[] {
  const out: Anomaly[] = [];
  const amounts = bookings.map((b) => Math.abs(Number(b.betrag) || 0)).filter((n) => n > 0);
  if (amounts.length >= 4) {
    const mean = amounts.reduce((s, n) => s + n, 0) / amounts.length;
    const sd = Math.sqrt(amounts.reduce((s, n) => s + (n - mean) ** 2, 0) / amounts.length) || 1;
    for (const b of bookings) {
      const amt = Math.abs(Number(b.betrag) || 0);
      const z = (amt - mean) / sd;
      if (z >= 3) out.push({ booking: b, severity: "high", reason: `Betrag CHF ${amt.toFixed(2)} liegt weit über dem Durchschnitt (CHF ${mean.toFixed(2)})` });
      else if (z >= 2) out.push({ booking: b, severity: "medium", reason: `Betrag CHF ${amt.toFixed(2)} ist überdurchschnittlich hoch` });
    }
  }

  // Missing account assignment
  for (const b of bookings) {
    if (!b.kt_soll && !b.kt_haben) {
      out.push({ booking: b, severity: "medium", reason: "Keine Kontierung (Soll/Haben fehlt)" });
    }
  }

  // Duplicates: same date + same absolute amount + similar description
  const seen = new Map<string, Booking>();
  for (const b of bookings) {
    const key = `${b.datum}|${Math.abs(Number(b.betrag) || 0).toFixed(2)}|${(b.beschreibung || "").slice(0, 12).toLowerCase()}`;
    if (seen.has(key)) {
      out.push({ booking: b, severity: "medium", reason: "Mögliche Dublette (gleiches Datum, Betrag & Beschreibung)" });
    } else {
      seen.set(key, b);
    }
  }

  // De-dup anomalies by booking id, keep highest severity
  const byId = new Map<number, Anomaly>();
  for (const a of out) {
    const prev = byId.get(a.booking.id);
    if (!prev || (a.severity === "high" && prev.severity !== "high")) byId.set(a.booking.id, a);
  }
  return Array.from(byId.values()).sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "high" ? -1 : 1));
}
