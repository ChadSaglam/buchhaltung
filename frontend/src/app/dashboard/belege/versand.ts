/**
 * Rechnung per E-Mail verschicken (B-79) — the pure parts.
 *
 * The dialog is the same contract as the Mahnung (B-65): the owner reads what
 * the customer will get before anything leaves the house. What lives here is
 * the wording and the "can this go out" decision, because those are the parts
 * worth testing without a browser.
 */
import type { Schemas } from "@/lib/api-schema";
import { formatDate } from "@/lib/format";

export type VersandEntwurf = Schemas["VersandEntwurfOut"];
export type VersandErgebnis = Schemas["VersandErgebnis"];

/** What the send button says, and whether it is a first send or a repeat. */
export function versandLabel(draft: VersandEntwurf | null | undefined): string {
  if (!draft) return "Per E-Mail senden";
  return draft.schon_gesendet_am ? "Nochmals senden" : "Senden";
}

/** One line explaining why the button is off — never a silent disabled control. */
export function versandGrund(draft: VersandEntwurf | null | undefined): string {
  if (!draft || draft.bereit) return "";
  const fehlt = draft.fehlt ?? [];
  if (fehlt.length === 0) return "Versand ist noch nicht möglich.";
  return `Es fehlt: ${fehlt.join(", ")}.`;
}

/** An invoice that went out already, for the list badge. */
export function gesendetLabel(sentAt: string | null | undefined): string {
  return sentAt ? `Gesendet ${formatDate(sentAt)}` : "";
}

/** Only send what the owner actually changed — the server fills the rest. */
export function versandBody(
  draft: VersandEntwurf,
  edited: { empfaenger: string; subject: string; text: string },
): Record<string, string> {
  const body: Record<string, string> = {};
  if (edited.empfaenger.trim() !== draft.empfaenger) body.empfaenger = edited.empfaenger.trim();
  if (edited.subject.trim() !== draft.subject) body.subject = edited.subject.trim();
  if (edited.text !== draft.text) body.text = edited.text;
  return body;
}
