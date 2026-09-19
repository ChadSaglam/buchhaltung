/**
 * B-103: the address in the QR payment part was wrong, and the payment part was real.
 *
 * First invoicing run, 2026-09-19. The Firmenprofil had two inputs under one
 * heading, «Strasse und Nr.» — a wide one and a narrow one. The owner wrote
 * `Bungertenstrasse 57` into the wide one (street *with* number, the way one
 * writes an address) and `485A` into the narrow one. `swiss_qr` joins them as
 * `StrtNmOrAdrLine1` + `BldgNbOrAdrLine2`, so Rechnung 2026-0001 carried
 * `Bungertenstrasse 57 485A, 8307 Illnau-Effretikon` — an address that does not
 * exist — on both the Empfangsschein and the Zahlteil.
 *
 * Separate labels alone would only repeat what the heading already said. The
 * warning is the part that actually catches it.
 */

/** A trailing number on a street name: "Bungertenstrasse 57", "Rue du Pont 12b". */
const HAUSNUMMER_AM_ENDE = /\s\d+\s*[a-zA-Z]?$/;

export function strasseEnthaeltNummer(strasse: string): boolean {
  return HAUSNUMMER_AM_ENDE.test((strasse ?? "").trim());
}

/**
 * The sentence to show under the street field, or "" when there is nothing to say.
 *
 * Only warns when *both* fields would end up in the QR code: a number in the
 * street field on its own is how a one-field address looks, and that is fine —
 * it reaches `StrtNmOrAdrLine1` unchanged and reads correctly.
 */
export function adressWarnung(strasse: string, hausnummer: string): string {
  if (!strasseEnthaeltNummer(strasse) || !(hausnummer ?? "").trim()) return "";
  const nummer = strasse.trim().match(HAUSNUMMER_AM_ENDE)?.[0].trim() ?? "";
  return (
    `Sieht doppelt aus: «${strasse.trim()}» endet schon auf ${nummer}, und im Feld Nr. steht ` +
    `«${hausnummer.trim()}». Im Zahlteil stünde dann «${strasse.trim()} ${hausnummer.trim()}».`
  );
}
