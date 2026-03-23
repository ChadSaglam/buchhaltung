export function calcMwst(betrag: number, pct: string): number {
  if (!pct || !betrag) return 0;
  const p = Math.abs(parseFloat(pct));
  const val = (betrag * p) / (100 + p);
  return parseFloat(pct) < 0 ? -Math.round(val * 100) / 100 : Math.round(val * 100) / 100;
}

export function sourceIcon(source: string) {
  return source === "Gedächtnis" ? "🧠" : source === "ML" ? "🤖" : "📋";
}

export function modelDisplayName(name: string, visionModels: string[]): string {
  if (!name) return "Unbekanntes Modell";
  const isVision = visionModels.includes(name);
  const isCloud = name.endsWith(":cloud") || name.endsWith("-cloud");
  if (isVision && isCloud) return `⚡👁 ${name}`;
  if (isVision) return `👁 ${name}`;
  if (isCloud) return `⚡ ${name}`;
  return name;
}

export function formatCHF(amount: number | null | undefined): string {
  const num = Number(amount);
  if (!Number.isFinite(num)) return "CHF 0.00";
  return new Intl.NumberFormat("de-CH", { style: "currency", currency: "CHF" }).format(num);
}
