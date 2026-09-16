/**
 * Heute — the inbox (`docs/IA-2026-09-14.md`, step 4 of the migration path).
 *
 * "Decisions come to the user, the user never hunts for them." Until now Heute
 * was a wall of cards: each one correct, each one asking to be read and compared
 * before you could tell whether anything needed doing. This turns the same SWR
 * data into rows — one per thing that is actually waiting — and leaves the cards
 * underneath as the detail.
 *
 * Everything here is pure. No number is recomputed; the rows only decide what is
 * worth interrupting someone for, in which order, and in what words.
 *
 * Two rows link to an anchor rather than a route. Liquidität and Dauerbuchungen
 * have no page of their own: their detail *is* the card below, so the row scrolls
 * to it. Pretending otherwise would mean inventing a page to link to.
 */
import type { Schemas } from "@/lib/api-schema";
import { formatCHF } from "@/lib/format";
import { kurzdatum } from "@/lib/liquiditaet";

export type HeuteTone = "danger" | "warning" | "info";

export interface HeuteRow {
  /** Stable across refreshes so React keeps the row, not its position. */
  id: string;
  titel: string;
  satz: string;
  href: string;
  aktion: string;
  tone: HeuteTone;
}

export interface HeuteSources {
  posten?: Schemas["OffenePostenResponse"];
  abgleich?: Schemas["AbgleichResponse"];
  review?: Schemas["ReviewQueueResponse"];
  email?: Schemas["EmailEingangResponse"];
  dauer?: Schemas["DauerbuchungenResponse"];
  liquiditaet?: Schemas["LiquiditaetResponse"];
}

const RANG: Record<HeuteTone, number> = { danger: 0, warning: 1, info: 2 };

function plural(n: number, eins: string, viele: string): string {
  return n === 1 ? `1 ${eins}` : `${n} ${viele}`;
}

export function inboxRows(sources: HeuteSources): HeuteRow[] {
  const rows: HeuteRow[] = [];
  const { posten, abgleich, review, email, dauer, liquiditaet } = sources;

  // Money that is late is the only thing that gets worse by itself.
  const debitoren = posten?.debitoren;
  if (debitoren && debitoren.overdue_count > 0) {
    rows.push({
      id: "debitoren-ueberfaellig",
      titel: `${plural(debitoren.overdue_count, "Rechnung überfällig", "Rechnungen überfällig")}`,
      satz: `${formatCHF(debitoren.overdue_total)} hätten bezahlt sein sollen.`,
      href: "#offene-posten",
      aktion: "Mahnen",
      tone: "danger",
    });
  }

  const kreditoren = posten?.kreditoren;
  if (kreditoren && kreditoren.overdue_count > 0) {
    rows.push({
      id: "kreditoren-ueberfaellig",
      titel: `${plural(kreditoren.overdue_count, "Lieferantenrechnung überfällig", "Lieferantenrechnungen überfällig")}`,
      satz: `${formatCHF(kreditoren.overdue_total)} sind fällig.`,
      href: "#offene-posten",
      aktion: "Ansehen",
      tone: "warning",
    });
  }

  if (liquiditaet && liquiditaet.tiefster_stand < 0) {
    rows.push({
      id: "liquiditaet-unter-null",
      titel: "Das Konto geht ins Minus",
      satz: `Am ${kurzdatum(liquiditaet.tiefster_am)} fehlen ${formatCHF(Math.abs(liquiditaet.tiefster_stand))}.`,
      href: "#liquiditaet",
      aktion: "Ansehen",
      tone: "danger",
    });
  }

  const fehlen = dauer?.fehlen ?? [];
  if (fehlen.length > 0) {
    const summe = fehlen.reduce((total, e) => total + e.betrag, 0);
    rows.push({
      id: "dauerbuchung-fehlt",
      titel:
        fehlen.length === 1
          ? `${fehlen[0].label} ist diesen Monat nicht rausgegangen`
          : `${fehlen.length} monatliche Zahlungen fehlen`,
      satz: `${formatCHF(summe)} — der übliche Termin ist durch.`,
      href: "#dauerbuchungen",
      aktion: "Ansehen",
      tone: "warning",
    });
  }

  const offeneZeilen = abgleich?.summary?.offene_zeilen ?? 0;
  if (offeneZeilen > 0) {
    rows.push({
      id: "bank-offene-zeilen",
      titel: `${plural(offeneZeilen, "Bankzeile ohne Beleg", "Bankzeilen ohne Beleg")}`,
      satz: "Ohne Beleg bleibt die Buchung offen.",
      href: "/dashboard/bank/abgleich",
      aktion: "Abgleichen",
      tone: "warning",
    });
  }

  if (review && review.count > 0) {
    rows.push({
      id: "review-offen",
      titel: `${plural(review.count, "Buchung unsicher", "Buchungen unsicher")}`,
      satz: "Bestätigen oder korrigieren — das Modell lernt daraus.",
      href: "/dashboard/review",
      aktion: "Prüfen",
      tone: "warning",
    });
  }

  if (email && email.abgelehnt > 0) {
    rows.push({
      id: "email-abgelehnt",
      titel: `${plural(email.abgelehnt, "E-Mail abgelehnt", "E-Mails abgelehnt")}`,
      satz: "Der Absender ist nicht freigegeben.",
      href: "/dashboard/belege/email",
      aktion: "Freigeben",
      tone: "warning",
    });
  }

  const vorschlaege = abgleich?.summary?.vorschlaege ?? 0;
  if (vorschlaege > 0) {
    rows.push({
      id: "abgleich-vorschlaege",
      titel: `${plural(vorschlaege, "Vorschlag wartet", "Vorschläge warten")}`,
      satz: "Beleg und Bankzeile passen zusammen — nur noch bestätigen.",
      href: "/dashboard/bank/abgleich",
      aktion: "Bestätigen",
      tone: "info",
    });
  }

  if (email && email.belege_24h > 0) {
    rows.push({
      id: "email-neue-belege",
      titel: `${plural(email.belege_24h, "neuer Beleg per E-Mail", "neue Belege per E-Mail")}`,
      satz: "In den letzten 24 Stunden eingetroffen.",
      href: "/dashboard/belege/email",
      aktion: "Ansehen",
      tone: "info",
    });
  }

  const steuer = liquiditaet?.steuer;
  if (steuer && (steuer.pro_quartal ?? 0) > 0) {
    rows.push({
      id: "steuer-zuruecklegen",
      titel: "Steuern zurücklegen",
      satz: `Dieses Quartal ${formatCHF(steuer.pro_quartal)} auf die Seite legen.`,
      href: "#liquiditaet",
      aktion: "Ansehen",
      tone: "info",
    });
  }

  // Stable sort: within a severity the order above is the order on screen, and
  // a number that changes must never make rows jump past each other.
  return rows.sort((a, b) => RANG[a.tone] - RANG[b.tone]);
}

/** The headline over the list — or the one line that means there is no list. */
export function inboxKopf(rows: HeuteRow[], isLoading: boolean): string {
  if (isLoading) return "Wird geladen …";
  if (rows.length === 0) return "Alles erledigt 🎉";
  return rows.length === 1 ? "Eine Sache wartet auf Sie" : `${rows.length} Sachen warten auf Sie`;
}

/** An anchor row scrolls down this page; everything else is a real route. */
export function istAnker(row: HeuteRow): boolean {
  return row.href.startsWith("#");
}
