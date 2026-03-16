'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page_header';

interface TxRow { Nr: number; Datum: string; Beschreibung: string; KtSoll: string; KtHaben: string; 'Betrag CHF': number; 'MwStUSt-Code': string; 'MwSt-%': string; 'Gebuchte MwStUSt CHF': number; }

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

  const COLS = ['Nr', 'Datum', 'Beschreibung', 'KtSoll', 'KtHaben', 'Betrag CHF', 'MwStUSt-Code', 'MwSt-%'];

  return (
    <div className="p-4 md:p-8 max-w-7xl">
      <PageHeader icon="📄" title="Kontoauszug" subtitle="UBS Kontoauszug PDF hochladen → Bearbeiten → Export" />

      {rows.length === 0 && !parsing && (
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) processFile(f); }}
          onClick={() => document.getElementById('pdf-input')?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 md:p-16 text-center cursor-pointer transition-all bg-white ${
            dragOver ? 'border-brand-500 bg-brand-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <div className="text-5xl mb-4">📄</div>
          <p className="text-gray-700 font-medium text-lg">PDF hier ablegen oder klicken</p>
          <p className="text-gray-400 text-sm mt-2">UBS Kontoauszug (.pdf)</p>
          <input id="pdf-input" type="file" accept=".pdf" onChange={e => e.target.files?.[0] && processFile(e.target.files[0])} className="hidden" />
        </div>
      )}

      {(parsing || classifying) && (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <div className="animate-spin text-4xl mb-4">🔄</div>
          <p className="text-gray-500">{classifying ? 'Transaktionen werden klassifiziert...' : 'PDF wird verarbeitet...'}</p>
        </div>
      )}

      {rows.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-sm text-gray-500">{rows.length} Transaktionen</span>
            <div className="flex-1" />
            <button onClick={() => handleExport('banana')} className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-sm">🍌 Banana TXT</button>
            <button onClick={() => handleExport('excel')} className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-sm">📊 Excel</button>
            <button onClick={() => handleExport('csv')} className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-sm">📋 CSV</button>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
            <table className="w-full text-sm min-w-[800px]">
              <thead><tr className="bg-gray-50 border-b border-gray-200 text-left">
                {COLS.map(h => <th key={h} className="px-3 py-3 font-medium text-gray-500 whitespace-nowrap">{h}</th>)}
              </tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50/50">
                    <td className="px-3 py-2 text-gray-400 w-12">{r.Nr}</td>
                    <td className="px-3 py-2"><input value={r.Datum} onChange={e => updateRow(i, 'Datum', e.target.value)} className="w-24 bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5" /></td>
                    <td className="px-3 py-2"><input value={r.Beschreibung} onChange={e => updateRow(i, 'Beschreibung', e.target.value)} className="w-full bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5 min-w-[200px]" /></td>
                    <td className="px-3 py-2"><input value={r.KtSoll} onChange={e => updateRow(i, 'KtSoll', e.target.value)} className="w-16 bg-transparent font-mono text-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5" /></td>
                    <td className="px-3 py-2"><input value={r.KtHaben} onChange={e => updateRow(i, 'KtHaben', e.target.value)} className="w-16 bg-transparent font-mono text-green-600 focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5" /></td>
                    <td className="px-3 py-2 font-mono text-right">{(r['Betrag CHF'] || 0).toFixed(2)}</td>
                    <td className="px-3 py-2"><input value={r['MwStUSt-Code']} onChange={e => updateRow(i, 'MwStUSt-Code', e.target.value)} className="w-12 bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5" /></td>
                    <td className="px-3 py-2 text-gray-500">{r['MwSt-%']}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-3">
            <button onClick={handleSave} disabled={saving || saved}
              className={`px-6 py-2.5 rounded-lg font-medium text-white text-sm transition-colors shadow-sm ${
                saved ? 'bg-green-600' : 'bg-brand-600 hover:bg-brand-700'
              } disabled:opacity-50`}>
              {saved ? '✅ Gespeichert!' : saving ? 'Speichert...' : '💾 Buchungen speichern'}
            </button>
            <button onClick={() => { setRows([]); setSaved(false); }} className="px-4 py-2.5 text-sm text-gray-500 hover:text-gray-700">
              ↺ Neue Datei
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
