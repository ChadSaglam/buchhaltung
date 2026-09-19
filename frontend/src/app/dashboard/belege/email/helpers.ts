/** Does this sender already have permission? Mirrors services/email_intake.sender_allowed. */
export function absenderBekannt(from: string, absender: string[]): boolean {
  const sender = (from ?? "").trim().toLowerCase();
  if (!sender) return false;
  const domain = sender.slice(sender.indexOf("@"));
  return (absender ?? []).some((entry) => {
    const e = entry.trim().toLowerCase();
    if (!e) return false;
    if (e === "*") return true;
    if (e.startsWith("@")) return domain === e;
    return e === sender;
  });
}

/** "3 neue Belege per E-Mail" — German plural without a library. */
export function belegeTitel(anzahl: number): string {
  if (anzahl <= 0) return "Belege per E-Mail";
  return anzahl === 1 ? "1 neuer Beleg per E-Mail" : `${anzahl} neue Belege per E-Mail`;
}
