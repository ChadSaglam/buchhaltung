"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import {
  Sparkles, Search, AlertTriangle, TrendingUp, TrendingDown,
  Wand2, Loader2, Info, RefreshCw,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { getBookings, aiSummary, type Booking } from "@/lib/api";
import {
  parseQuery, searchBookings, monthlyStats, detectAnomalies,
  type Anomaly, type MonthlyStats,
} from "@/lib/booking-analytics";
import { cn } from "@/lib/utils";

function chf(n: number) {
  return `CHF ${n.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const EXAMPLES = [
  "Ausgaben über 500 im Juni",
  "Migros Lebensmittel",
  "Einnahmen 2026",
  "Konto 6500",
];

export default function InsightsPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  // AI summary state
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryFallback, setSummaryFallback] = useState(false);
  const [summarizing, setSummarizing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getBookings(undefined, 1000);
      setBookings((data as Booking[]) ?? []);
    } catch {
      setBookings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const parsed = useMemo(() => parseQuery(query), [query]);
  const results = useMemo(
    () => (query.trim() ? searchBookings(bookings, parsed) : bookings),
    [bookings, parsed, query]
  );
  const months: MonthlyStats[] = useMemo(() => monthlyStats(bookings), [bookings]);
  const anomalies: Anomaly[] = useMemo(() => detectAnomalies(bookings), [bookings]);

  const activeFilters = useMemo(() => {
    const f: string[] = [];
    if (parsed.text) f.push(`Text: „${parsed.text}“`);
    if (parsed.minAmount != null) f.push(`≥ ${chf(parsed.minAmount)}`);
    if (parsed.maxAmount != null) f.push(`≤ ${chf(parsed.maxAmount)}`);
    if (parsed.month != null) f.push(`Monat ${parsed.month}`);
    if (parsed.year != null) f.push(`Jahr ${parsed.year}`);
    if (parsed.konto) f.push(`Konto ${parsed.konto}`);
    if (parsed.direction) f.push(parsed.direction === "credit" ? "Einnahmen" : "Ausgaben");
    return f;
  }, [parsed]);

  const runSummary = async () => {
    setSummarizing(true);
    setSummary(null);
    try {
      const res = await aiSummary();
      if (res.error || !res.content) {
        setSummaryFallback(true);
      } else {
        setSummary(res.content);
        setSummaryFallback(false);
      }
    } catch {
      setSummaryFallback(true);
    } finally {
      setSummarizing(false);
    }
  };

  const latest = months[0];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Sparkles}
        title="Insights & Suche"
        subtitle="Buchungen in natürlicher Sprache durchsuchen, Monatsauswertung und Auffälligkeiten"
        action={
          <Button variant="ghost" size="sm" icon={<RefreshCw className="h-4 w-4" />} onClick={load} disabled={loading}>
            Aktualisieren
          </Button>
        }
      />

      {/* Natural-language search */}
      <Card>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-3 focus-within:border-border-strong focus-within:ring-2 focus-within:ring-ring/30">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="z. B. Ausgaben über 500 im Juni  ·  Migros Lebensmittel  ·  Konto 6500"
              className="h-11 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
            {query && (
              <button onClick={() => setQuery("")} className="text-xs text-muted-foreground hover:text-foreground">
                Löschen
              </button>
            )}
          </div>

          {!query && (
            <div className="flex flex-wrap gap-1.5">
              <span className="text-xs text-muted-foreground">Beispiele:</span>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setQuery(ex)}
                  className="rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}

          {query && activeFilters.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              {activeFilters.map((f) => (
                <Badge key={f} tone="brand">{f}</Badge>
              ))}
              <span className="ml-1 text-xs text-muted-foreground">{results.length} Treffer</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Search results */}
      {query && (
        loading ? (
          <Card><CardContent className="flex items-center justify-center py-12 text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Laden…</CardContent></Card>
        ) : results.length === 0 ? (
          <EmptyState icon={Search} title="Keine Treffer" description="Passe deine Suche an oder lösche Filter." />
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead>
                  <tr className="border-b border-border bg-muted text-left">
                    <th className="px-3 py-3 font-medium text-muted-foreground">Datum</th>
                    <th className="px-3 py-3 font-medium text-muted-foreground">Beschreibung</th>
                    <th className="px-3 py-3 font-medium text-muted-foreground">Soll</th>
                    <th className="px-3 py-3 font-medium text-muted-foreground">Haben</th>
                    <th className="px-3 py-3 text-right font-medium text-muted-foreground">Betrag</th>
                  </tr>
                </thead>
                <tbody>
                  {results.slice(0, 200).map((b) => (
                    <tr key={b.id} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                      <td className="whitespace-nowrap px-3 py-2 text-muted-foreground tabular-nums">{b.datum}</td>
                      <td className="px-3 py-2 text-foreground">{b.beschreibung}</td>
                      <td className="px-3 py-2 font-mono text-brand-600 dark:text-brand-300">{b.kt_soll}</td>
                      <td className="px-3 py-2 font-mono text-success">{b.kt_haben}</td>
                      <td className={cn("px-3 py-2 text-right font-mono tabular-nums", (Number(b.betrag) || 0) < 0 ? "text-destructive" : "text-foreground")}>
                        {(Number(b.betrag) || 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {results.length > 200 && (
              <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
                Zeige die ersten 200 von {results.length} Treffern.
              </p>
            )}
          </Card>
        )
      )}

      {/* Monthly summary + anomalies (hidden while actively searching) */}
      {!query && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            {/* AI monthly summary */}
            <Card>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Wand2 className="h-4 w-4 text-brand-600 dark:text-brand-300" />
                    <h2 className="text-sm font-semibold text-foreground">AI-Monatszusammenfassung</h2>
                  </div>
                  <Button size="sm" onClick={runSummary} loading={summarizing} disabled={bookings.length === 0}>
                    Erstellen
                  </Button>
                </div>

                {latest ? (
                  <div className="grid grid-cols-3 gap-3">
                    <Metric label="Letzter Monat" value={latest.month} />
                    <Metric label="Ausgaben" value={chf(latest.totalDebit)} tone="down" />
                    <Metric label="Einnahmen" value={chf(latest.totalCredit)} tone="up" />
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Noch keine datierten Buchungen vorhanden.</p>
                )}

                {summarizing && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> AI erstellt die Zusammenfassung…
                  </div>
                )}
                {summary && (
                  <div className="rounded-lg border border-border bg-surface p-3 text-sm leading-relaxed text-foreground whitespace-pre-wrap">
                    {summary}
                  </div>
                )}
                {summaryFallback && (
                  <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-foreground">
                    <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                    <span>
                      Die AI-Zusammenfassung ist nicht verfügbar (Ollama offline). Die Kennzahlen und Auffälligkeiten unten
                      basieren weiterhin auf deinen echten Daten.
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Monthly breakdown */}
            {months.length > 0 && (
              <Card>
                <CardContent>
                  <h2 className="mb-3 text-sm font-semibold text-foreground">Monatsübersicht</h2>
                  <div className="space-y-2">
                    {months.slice(0, 6).map((m) => {
                      const max = Math.max(...months.slice(0, 6).map((x) => x.totalDebit + x.totalCredit), 1);
                      const w = ((m.totalDebit + m.totalCredit) / max) * 100;
                      return (
                        <div key={m.month} className="flex items-center gap-3">
                          <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground tabular-nums">{m.month}</span>
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                            <div className="h-full rounded-full bg-primary" style={{ width: `${w}%` }} />
                          </div>
                          <span className="w-16 shrink-0 text-right text-xs text-muted-foreground tabular-nums">{m.count}×</span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Anomalies */}
          <div className="self-start">
            <Card>
              <CardContent>
                <div className="mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-warning" />
                  <h2 className="text-sm font-semibold text-foreground">Auffälligkeiten</h2>
                  {anomalies.length > 0 && <Badge tone="warning">{anomalies.length}</Badge>}
                </div>
                {loading ? (
                  <p className="text-sm text-muted-foreground">Analysiere…</p>
                ) : anomalies.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Keine Auffälligkeiten erkannt.</p>
                ) : (
                  <ul className="space-y-2">
                    {anomalies.slice(0, 12).map((a) => (
                      <li key={a.booking.id} className="rounded-lg border border-border bg-surface p-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-medium text-foreground">{a.booking.beschreibung || "—"}</span>
                          <Badge tone={a.severity === "high" ? "danger" : "warning"}>
                            {a.severity === "high" ? "Hoch" : "Mittel"}
                          </Badge>
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">{a.reason}</p>
                        <p className="mt-0.5 text-[11px] text-muted-foreground/70 tabular-nums">
                          {a.booking.datum} · {chf(Math.abs(Number(a.booking.betrag) || 0))}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {tone === "up" && <TrendingUp className="h-3 w-3 text-success" />}
        {tone === "down" && <TrendingDown className="h-3 w-3 text-destructive" />}
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold text-foreground tabular-nums">{value}</p>
    </div>
  );
}
