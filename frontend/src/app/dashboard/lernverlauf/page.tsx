'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page_header';
import { MetricCard } from '@/components/ui/metric_card';

interface MemoryEntry { lookup_key: string; kt_soll: string; kt_haben: string; mwst_code: string; mwst_pct: string; }
interface CorrectionEntry { beschreibung: string; original_soll: string; original_haben: string; corrected_soll: string; corrected_haben: string; corrected_mwst_code: string; created_at: string | null; }
interface ChartItem { account?: string; source?: string; count: number; }
interface LearningStats { memory_count: number; correction_count: number; booking_count: number; memory_distribution: ChartItem[]; correction_distribution: ChartItem[]; source_distribution: ChartItem[]; }

function HBar({ data, labelKey, title, color }: { data: ChartItem[]; labelKey: 'account' | 'source'; title: string; color: string }) {
  if (!data.length) return <p className="text-gray-400 text-sm py-4">Keine Daten vorhanden</p>;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div>
      <h3 className="font-semibold text-gray-900 mb-3 text-sm">{title}</h3>
      <div className="space-y-2">
        {data.map((item, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-gray-500 w-16 text-right font-mono truncate">{item[labelKey] || '—'}</span>
            <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
              <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${(item.count / max) * 100}%` }} />
            </div>
            <span className="text-xs text-gray-500 w-8 text-right">{item.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function LernverlaufPage() {
  const [tab, setTab] = useState<'charts' | 'memory' | 'corrections'>('charts');
  const [memory, setMemory] = useState<MemoryEntry[]>([]);
  const [corrections, setCorrections] = useState<CorrectionEntry[]>([]);
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [info, setInfo] = useState<{ memory_count: number; correction_count: number } | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/api/classify/memory').then(r => setMemory(r.data.entries || [])),
      api.get('/api/classify/corrections').then(r => setCorrections(r.data.corrections || [])),
      api.get('/api/stats/learning').then(r => setStats(r.data)),
      api.get('/api/classify/info').then(r => setInfo(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const filteredMemory = memory.filter(m => !search || m.lookup_key.includes(search.toLowerCase()) || m.kt_soll.includes(search));
  const filteredCorrections = corrections.filter(c => !search || c.beschreibung.toLowerCase().includes(search.toLowerCase()));

  if (loading) return <div className="p-8 text-gray-400">Laden...</div>;

  return (
    <div className="p-8 max-w-6xl">
      <PageHeader icon="📊" title="Lernverlauf" subtitle="Korrekturen, Gedächtnis und Modell-Statistiken" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Gedächtnis" value={info?.memory_count || 0} accent="blue" />
        <MetricCard title="Korrekturen" value={info?.correction_count || 0} accent="amber" />
        <MetricCard title="Buchungen" value={stats?.booking_count || 0} accent="green" />
        <MetricCard title="Konten gelernt" value={stats?.memory_distribution?.length || 0} accent="gray" />
      </div>

      {/* Tabs */}
      <div className="flex items-center border-b border-gray-200 mb-6 gap-4">
        <div className="flex">
          {(['charts', 'memory', 'corrections'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t ? 'border-brand-600 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
              {t === 'charts' ? 'Statistiken' : t === 'memory' ? 'Gedächtnis' : 'Korrekturen'}
            </button>
          ))}
        </div>
        {tab !== 'charts' && (
          <input type="text" placeholder="Suchen..." value={search} onChange={e => setSearch(e.target.value)}
            className="ml-auto px-3 py-1.5 border border-gray-200 rounded-lg text-sm w-56 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" />
        )}
      </div>

      {tab === 'charts' && stats && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <HBar data={stats.memory_distribution} labelKey="account" title="Gedächtnis nach Konto" color="bg-brand-500" />
          </div>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <HBar data={stats.correction_distribution} labelKey="account" title="Korrekturen nach Konto" color="bg-amber-500" />
          </div>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 md:col-span-2">
            <HBar data={stats.source_distribution} labelKey="source" title="Buchungen nach Quelle" color="bg-green-500" />
          </div>
        </div>
      )}

      {tab === 'memory' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-200 text-left">
              <th className="px-4 py-3 font-medium text-gray-500">Beschreibung</th>
              <th className="px-4 py-3 font-medium text-gray-500">KtSoll</th>
              <th className="px-4 py-3 font-medium text-gray-500">KtHaben</th>
              <th className="px-4 py-3 font-medium text-gray-500">MwSt</th>
            </tr></thead>
            <tbody>
              {filteredMemory.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">Gedächtnis ist leer</td></tr>
              ) : filteredMemory.map((m, i) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50/50">
                  <td className="px-4 py-2.5 text-gray-700">{m.lookup_key}</td>
                  <td className="px-4 py-2.5 font-mono text-brand-600">{m.kt_soll}</td>
                  <td className="px-4 py-2.5 font-mono text-green-600">{m.kt_haben}</td>
                  <td className="px-4 py-2.5 text-gray-500">{m.mwst_code} {m.mwst_pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'corrections' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b border-gray-200 text-left">
              <th className="px-4 py-3 font-medium text-gray-500">Zeitpunkt</th>
              <th className="px-4 py-3 font-medium text-gray-500">Beschreibung</th>
              <th className="px-4 py-3 font-medium text-gray-500">Original → Korrigiert</th>
            </tr></thead>
            <tbody>
              {filteredCorrections.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-8 text-center text-gray-400">Keine Korrekturen</td></tr>
              ) : filteredCorrections.map((c, i) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50/50">
                  <td className="px-4 py-2.5 text-gray-400 text-xs">{c.created_at?.slice(0, 16).replace('T', ' ') || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-700">{c.beschreibung}</td>
                  <td className="px-4 py-2.5">
                    <span className="text-red-500 font-mono">{c.original_soll}</span>
                    <span className="text-gray-400 mx-1.5">→</span>
                    <span className="text-green-600 font-mono">{c.corrected_soll}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
