'use client';
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { FileText, Upload, Loader2, Save, RefreshCw, Download, Sparkles, Check } from 'lucide-react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page_header';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/shared/EmptyState';

interface TxRow {
  Nr: number; Datum: string; Beschreibung: string; KtSoll: string; KtHaben: string;
  'Betrag CHF': number; 'MwStUSt-Code': string; 'MwSt-%': string; 'Gebuchte MwStUSt CHF': number;
  confidence?: number; source?: string; suggSoll?: string; suggHaben?: string; accepted?: boolean;
}

/** Map an AI confidence score to a badge tone + label. */
function confidenceTone(c?: number): { tone: 'success' | 'warning' | 'danger' | 'neutral'; label: string } {
  if (c == null) return { tone: 'neutral', label: '—' };
  const pct = Math.round(c * 100);
  if (c >= 0.8) return { tone: 'success', label: `${pct}%` };
  if (c >= 0.5) return { tone: 'warning', label: `${pct}%` };
  return { tone: 'danger', label: `${pct}%` };
}

export default function KontoauszugPage() {
  const [parsing, setParsing] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [rows, setRows] = useState<TxRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const processFile = async (file: File) => {
    setParsing(true); setRows([]); setSaved(false);
    try {
      const form = new FormData(); form.append('file', file);
      const parseRes = await api.post('/api/pdf/parse', form);
      const transactions = parseRes.data.transactions || [];

      setClassifying(true);
      const classRes = await api.post('/api/classify/batch', { transactions });
      const results = classRes.data.results || [];

      setRows(results.map((r: Record<string, unknown>, i: number) => ({
        Nr: i + 1,
        Datum: (r.datum as string) || '',
        Beschreibung: (r.beschreibung as string) || '',
        KtSoll: (r.kt_soll as string) || '',
        KtHaben: (r.kt_haben as string) || '',
        'Betrag CHF': Number(r.betrag) || 0,
        'MwStUSt-Code': (r.mwst_code as string) || '',
        'MwSt-%': (r.mwst_pct as string) || '',
        'Gebuchte MwStUSt CHF': Number(r.mwst_amount) || 0,
        confidence: typeof r.confidence === 'number' ? (r.confidence as number) : undefined,
        source: (r.source as string) || undefined,
        suggSoll: (r.kt_soll as string) || '',
        suggHaben: (r.kt_haben as string) || '',
        accepted: false,
      })));
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Fehler beim Verarbeiten');
    } finally { setParsing(false); setClassifying(false); }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post('/api/bookings/', rows.map(r => ({
        datum: r.Datum, beschreibung: r.Beschreibung, betrag: r['Betrag CHF'],
        kt_soll: r.KtSoll, kt_haben: r.KtHaben, mwst_code: r['MwStUSt-Code'],
        mwst_pct: r['MwSt-%'], mwst_amount: r['Gebuchte MwStUSt CHF'], source: 'kontoauszug',
      })));
      for (const r of rows) {
        if (r.KtSoll) await api.post('/api/classify/correct', {
          beschreibung: r.Beschreibung, original_soll: r.KtSoll, original_haben: r.KtHaben,
          corrected_soll: r.KtSoll, corrected_haben: r.KtHaben,
        }).catch(() => {});
      }
      setSaved(true);
    } finally { setSaving(false); }
  };

  const handleExport = async (format: 'banana' | 'excel' | 'csv') => {
    try {
      const res = await api.get(`/api/export/${format}`, { params: { source: 'kontoauszug' }, responseType: 'blob' });
      const ext = format === 'banana' ? 'txt' : format === 'excel' ? 'xlsx' : 'csv';
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = url; a.download = `buchhaltung.${ext}`; a.click();
    } catch { alert('Export fehlgeschlagen — keine Buchungen vorhanden?'); }
  };

  const updateRow = (idx: number, field: string, value: string | number) => setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));

  const acceptSuggestion = (idx: number) => setRows(prev => prev.map((r, i) =>
    i === idx ? { ...r, KtSoll: r.suggSoll ?? r.KtSoll, KtHaben: r.suggHaben ?? r.KtHaben, accepted: true } : r
  ));
  const acceptAll = () => setRows(prev => prev.map((r) => ({
    ...r, KtSoll: r.suggSoll ?? r.KtSoll, KtHaben: r.suggHaben ?? r.KtHaben, accepted: true,
  })));
  const lowConfidenceCount = rows.filter(r => (r.confidence ?? 1) < 0.8).length;

  const COLS = ['Nr', 'Datum', 'Beschreibung', 'KtSoll', 'KtHaben', 'Betrag CHF', 'MwSt', 'AI', ''];

  return (
    <div>
      <PageHeader
        icon={FileText}
        title="Kontoauszug"
        subtitle="UBS Kontoauszug PDF hochladen → Bearbeiten → Export"
      />

      <AnimatePresence mode="wait">
        {rows.length === 0 && !parsing && (
          <motion.div
            key="dropzone"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) processFile(f); }}
            onClick={() => document.getElementById('pdf-input')?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 md:p-16 text-center cursor-pointer transition-all ${
              dragOver ? 'border-brand-500 bg-brand-500/8' : 'border-border hover:border-brand-400 hover:bg-accent/50'
            }`}
          >
            <div className="flex justify-center mb-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-300">
                <Upload className="h-8 w-8" />
              </div>
            </div>
            <p className="text-foreground font-semibold text-base">PDF hier ablegen oder klicken</p>
            <p className="text-muted-foreground text-sm mt-2">UBS Kontoauszug (.pdf)</p>
            <input id="pdf-input" type="file" accept=".pdf" onChange={e => e.target.files?.[0] && processFile(e.target.files[0])} className="hidden" />
          </motion.div>
        )}

        {(parsing || classifying) && (
          <motion.div
            key="processing"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <Card>
              <CardContent className="flex flex-col items-center py-16">
                <Loader2 className="h-10 w-10 animate-spin text-brand-600 dark:text-brand-300 mb-4" />
                <p className="text-muted-foreground">
                  {classifying ? 'Transaktionen werden klassifiziert...' : 'PDF wird verarbeitet...'}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {rows.length > 0 && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="space-y-4"
          >
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-sm text-muted-foreground">{rows.length} Transaktionen</span>
              {lowConfidenceCount > 0 && <Badge tone="warning">{lowConfidenceCount} unsicher</Badge>}
              <Button variant="secondary" size="sm" icon={<Sparkles className="h-3.5 w-3.5" />} onClick={acceptAll}>
                Alle AI-Vorschläge übernehmen
              </Button>
              <div className="flex-1" />
              <Button variant="outline" size="sm" icon={<Download className="h-3.5 w-3.5" />} onClick={() => handleExport('banana')}>Banana TXT</Button>
              <Button variant="outline" size="sm" icon={<Download className="h-3.5 w-3.5" />} onClick={() => handleExport('excel')}>Excel</Button>
              <Button variant="outline" size="sm" icon={<Download className="h-3.5 w-3.5" />} onClick={() => handleExport('csv')}>CSV</Button>
            </div>

            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[800px]">
                  <thead>
                    <tr className="bg-muted border-b border-border text-left">
                      {COLS.map(h => <th key={h} className="px-3 py-3 font-medium text-muted-foreground whitespace-nowrap">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={i} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                        <td className="px-3 py-2 text-muted-foreground w-12 tabular-nums">{r.Nr}</td>
                        <td className="px-3 py-2"><input value={r.Datum} onChange={e => updateRow(i, 'Datum', e.target.value)} className="w-24 bg-transparent focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5 text-foreground" /></td>
                        <td className="px-3 py-2"><input value={r.Beschreibung} onChange={e => updateRow(i, 'Beschreibung', e.target.value)} className="w-full bg-transparent focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5 min-w-[200px] text-foreground" /></td>
                        <td className="px-3 py-2"><input value={r.KtSoll} onChange={e => updateRow(i, 'KtSoll', e.target.value)} className="w-16 bg-transparent font-mono text-brand-600 dark:text-brand-300 focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5" /></td>
                        <td className="px-3 py-2"><input value={r.KtHaben} onChange={e => updateRow(i, 'KtHaben', e.target.value)} className="w-16 bg-transparent font-mono text-success focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5" /></td>
                        <td className="px-3 py-2 font-mono text-right tabular-nums text-foreground">{(r['Betrag CHF'] || 0).toFixed(2)}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <input value={r['MwStUSt-Code']} onChange={e => updateRow(i, 'MwStUSt-Code', e.target.value)} className="w-12 bg-transparent focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5 text-foreground" />
                          {r['MwSt-%'] && <span className="ml-1 text-xs text-muted-foreground tabular-nums">{r['MwSt-%']}</span>}
                        </td>
                        <td className="px-3 py-2">
                          {(() => { const t = confidenceTone(r.confidence); return (
                            <span title={r.source ? `Quelle: ${r.source}` : undefined} className="inline-flex">
                              <Badge tone={t.tone}>{t.label}</Badge>
                            </span>
                          ); })()}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {r.accepted ? (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-success"><Check className="h-3.5 w-3.5" /> Übernommen</span>
                          ) : (
                            <button
                              onClick={() => acceptSuggestion(i)}
                              className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
                              title="AI-Vorschlag für diese Zeile übernehmen"
                            >
                              <Sparkles className="h-3.5 w-3.5" /> Übernehmen
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="flex gap-3">
              <Button
                variant={saved ? 'success' : 'primary'}
                onClick={handleSave}
                disabled={saving || saved}
                loading={saving}
                icon={<Save className="h-4 w-4" />}
              >
                {saved ? 'Gespeichert!' : 'Buchungen speichern'}
              </Button>
              <Button variant="ghost" icon={<RefreshCw className="h-4 w-4" />} onClick={() => { setRows([]); setSaved(false); }}>
                Neue Datei
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
