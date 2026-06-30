'use client';
import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { GraduationCap, Search, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page_header';
import { MetricCard } from '@/components/ui/metric_card';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { EmptyState } from '@/components/shared/EmptyState';

interface MemoryEntry { lookup_key: string; kt_soll: string; kt_haben: string; mwst_code: string; mwst_pct: string; }
interface CorrectionEntry { beschreibung: string; original_soll: string; original_haben: string; corrected_soll: string; corrected_haben: string; corrected_mwst_code: string; created_at: string | null; }
interface ChartItem { account?: string; source?: string; count: number; }
interface LearningStats { memory_count: number; correction_count: number; booking_count: number; memory_distribution: ChartItem[]; correction_distribution: ChartItem[]; source_distribution: ChartItem[]; }

function HBar({ data, labelKey, title, colorClass }: { data: ChartItem[]; labelKey: 'account' | 'source'; title: string; colorClass: string }) {
  if (!data.length) return <p className="text-muted-foreground text-sm py-4">Keine Daten vorhanden</p>;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div>
      <h3 className="font-semibold text-foreground mb-3 text-sm">{title}</h3>
      <div className="space-y-2">
        {data.map((item, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground w-16 text-right font-mono truncate">{item[labelKey] || '—'}</span>
            <div className="flex-1 bg-muted rounded-full h-5 overflow-hidden">
              <div className={`h-full rounded-full ${colorClass} transition-all duration-500`} style={{ width: `${(item.count / max) * 100}%` }} />
            </div>
            <span className="text-xs text-muted-foreground w-8 text-right tabular-nums">{item.count}</span>
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

  if (loading) return (
    <div className="p-8 flex items-center gap-3 text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" /> Laden...
    </div>
  );

  return (
    <div className="p-8 max-w-6xl">
      <PageHeader icon={GraduationCap} title="Lernverlauf" subtitle="Korrekturen, Gedächtnis und Modell-Statistiken" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Gedächtnis" value={info?.memory_count || 0} accent="brand" />
        <MetricCard title="Korrekturen" value={info?.correction_count || 0} accent="warning" />
        <MetricCard title="Buchungen" value={stats?.booking_count || 0} accent="success" />
        <MetricCard title="Konten gelernt" value={stats?.memory_distribution?.length || 0} accent="neutral" />
      </div>

      {/* Tabs */}
      <div className="flex items-center border-b border-border mb-6 gap-4">
        <div className="flex">
          {(['charts', 'memory', 'corrections'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t ? 'border-brand-600 text-brand-600 dark:text-brand-300 dark:border-brand-300' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}>
              {t === 'charts' ? 'Statistiken' : t === 'memory' ? 'Gedächtnis' : 'Korrekturen'}
            </button>
          ))}
        </div>
        {tab !== 'charts' && (
          <div className="ml-auto relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input type="text" placeholder="Suchen..." value={search} onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 border border-input rounded-lg text-sm w-56 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring transition-all" />
          </div>
        )}
      </div>

      {tab === 'charts' && stats && (
        <div className="grid md:grid-cols-2 gap-6">
          {[
            { data: stats.memory_distribution, labelKey: 'account' as const, title: 'Gedächtnis nach Konto', colorClass: 'bg-brand-500' },
            { data: stats.correction_distribution, labelKey: 'account' as const, title: 'Korrekturen nach Konto', colorClass: 'bg-warning' },
            { data: stats.source_distribution, labelKey: 'source' as const, title: 'Buchungen nach Quelle', colorClass: 'bg-success', span: true },
          ].map((chart, i) => (
            <motion.div
              key={chart.title}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: i * 0.07 }}
              className={chart.span ? 'md:col-span-2' : ''}
            >
              <Card>
                <CardContent className="pt-5">
                  <HBar data={chart.data} labelKey={chart.labelKey} title={chart.title} colorClass={chart.colorClass} />
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {tab === 'memory' && (
        <Card>
          <div className="overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted border-b border-border text-left">
                  <th className="px-4 py-3 font-medium text-muted-foreground">Beschreibung</th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">KtSoll</th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">KtHaben</th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">MwSt</th>
                </tr>
              </thead>
              <tbody>
                {filteredMemory.length === 0 ? (
                  <tr><td colSpan={4}><EmptyState title="Gedächtnis ist leer" /></td></tr>
                ) : filteredMemory.map((m, i) => (
                  <motion.tr
                    key={i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2, delay: Math.min(i * 0.03, 0.3) }}
                    className="border-b border-border last:border-0 hover:bg-accent transition-colors"
                  >
                    <td className="px-4 py-2.5 text-foreground">{m.lookup_key}</td>
                    <td className="px-4 py-2.5 font-mono text-brand-600 dark:text-brand-300">{m.kt_soll}</td>
                    <td className="px-4 py-2.5 font-mono text-success">{m.kt_haben}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{m.mwst_code} {m.mwst_pct}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === 'corrections' && (
        <Card>
          <div className="overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted border-b border-border text-left">
                  <th className="px-4 py-3 font-medium text-muted-foreground">Zeitpunkt</th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">Beschreibung</th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">Original → Korrigiert</th>
                </tr>
              </thead>
              <tbody>
                {filteredCorrections.length === 0 ? (
                  <tr><td colSpan={3}><EmptyState title="Keine Korrekturen" /></td></tr>
                ) : filteredCorrections.map((c, i) => (
                  <motion.tr
                    key={i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2, delay: Math.min(i * 0.03, 0.3) }}
                    className="border-b border-border last:border-0 hover:bg-accent transition-colors"
                  >
                    <td className="px-4 py-2.5 text-muted-foreground text-xs tabular-nums">{c.created_at?.slice(0, 16).replace('T', ' ') || '—'}</td>
                    <td className="px-4 py-2.5 text-foreground">{c.beschreibung}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-destructive font-mono">{c.original_soll}</span>
                      <span className="text-muted-foreground mx-1.5">→</span>
                      <span className="text-success font-mono">{c.corrected_soll}</span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
