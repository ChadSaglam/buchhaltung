'use client';
import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { BookOpen, Plus, Save, Zap, X, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page_header';
import { MetricCard } from '@/components/ui/metric_card';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

interface Konto { konto: string; bezeichnung: string; }

export default function KontenplanPage() {
  const [tab, setTab] = useState<'kontenplan' | 'training'>('kontenplan');
  const [konten, setKonten] = useState<Konto[]>([]);
  const [classifyInfo, setClassifyInfo] = useState<{ model_accuracy: number; memory_count: number; correction_count: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    api.get('/api/kontenplan/').then(r => {
      const data = r.data?.kontenplan || r.data || {};
      setKonten(Object.entries(data).map(([k, v]) => ({ konto: k, bezeichnung: v as string })));
    });
    api.get('/api/classify/info').then(r => setClassifyInfo(r.data));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const obj: Record<string, string> = {};
      konten.forEach(k => { if (k.konto) obj[k.konto] = k.bezeichnung; });
      await api.put('/api/kontenplan/', { kontenplan: obj });
    } finally { setSaving(false); }
  };

  const handleTrain = async () => {
    setTraining(true);
    setTrainResult(null);
    try {
      const res = await api.post('/api/classify/train');
      setTrainResult(`Trainiert: ${res.data.total_samples} Daten, ${((res.data.cv_accuracy || 0) * 100).toFixed(0)}% Genauigkeit`);
      api.get('/api/classify/info').then(r => setClassifyInfo(r.data));
    } catch (e: unknown) {
      setTrainResult('Fehler: Nicht genug Daten zum Trainieren.');
    } finally { setTraining(false); }
  };

  const updateKonto = (idx: number, field: 'konto' | 'bezeichnung', value: string) => {
    setKonten(prev => prev.map((k, i) => i === idx ? { ...k, [field]: value } : k));
  };

  const filtered = konten.filter(k =>
    !search || k.konto.includes(search) || k.bezeichnung.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <PageHeader icon={BookOpen} title="Kontenplan & Training" subtitle="Kontenplan bearbeiten, Modell trainieren" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Genauigkeit" value={classifyInfo?.model_accuracy ? `${(classifyInfo.model_accuracy * 100).toFixed(0)}%` : '—'} accent="brand" />
        <MetricCard title="Konten" value={konten.length} accent="success" />
        <MetricCard title="Gedächtnis" value={classifyInfo?.memory_count || 0} accent="warning" />
        <MetricCard title="Korrekturen" value={classifyInfo?.correction_count || 0} accent="neutral" />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border mb-6">
        {(['kontenplan', 'training'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === t ? 'border-brand-600 text-brand-600 dark:text-brand-300 dark:border-brand-300' : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}>
            {t === 'kontenplan' ? 'Kontenplan' : 'Training'}
          </button>
        ))}
      </div>

      {tab === 'kontenplan' && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22 }}
        >
          <div className="flex gap-3 mb-4">
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text" placeholder="Suchen..." value={search} onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-input rounded-lg text-sm bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring transition-all"
              />
            </div>
            <div className="flex-1" />
            <Button
              variant="outline"
              size="sm"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setKonten(prev => [...prev, { konto: '', bezeichnung: '' }])}
            >
              Konto hinzufügen
            </Button>
          </div>
          <Card>
            <div className="overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted border-b border-border">
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32">Konto-Nr.</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Bezeichnung</th>
                    <th className="w-12" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((k, i) => {
                    const realIdx = konten.indexOf(k);
                    return (
                      <tr key={i} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                        <td className="px-4 py-2">
                          <input value={k.konto} onChange={e => updateKonto(realIdx, 'konto', e.target.value)}
                            className="w-full bg-transparent font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5" />
                        </td>
                        <td className="px-4 py-2">
                          <input value={k.bezeichnung} onChange={e => updateKonto(realIdx, 'bezeichnung', e.target.value)}
                            className="w-full bg-transparent text-foreground focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5" />
                        </td>
                        <td className="px-2">
                          <button
                            onClick={() => setKonten(prev => prev.filter((_, j) => j !== realIdx))}
                            className="rounded p-1 text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
                            aria-label="Konto löschen"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
          <div className="mt-4 flex gap-3">
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={saving}
              loading={saving}
              icon={<Save className="h-4 w-4" />}
            >
              {saving ? 'Speichert...' : 'Kontenplan speichern'}
            </Button>
          </div>
        </motion.div>
      )}

      {tab === 'training' && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Modell trainieren</CardTitle>
              <CardDescription>
                {classifyInfo?.correction_count
                  ? `${classifyInfo.correction_count} Korrekturen verfügbar zum Trainieren.`
                  : 'Noch keine Korrekturen vorhanden.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="success"
                onClick={handleTrain}
                disabled={training}
                loading={training}
                icon={<Zap className="h-4 w-4" />}
              >
                {training ? 'Trainiert...' : 'Jetzt trainieren'}
              </Button>
              {trainResult && (
                <div className={`mt-4 p-3 rounded-lg text-sm ${
                  trainResult.startsWith('Fehler')
                    ? 'bg-destructive/10 text-destructive border border-destructive/20'
                    : 'bg-success/10 text-success border border-success/20'
                }`}>
                  {trainResult}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
