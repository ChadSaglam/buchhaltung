'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page_header';
import { MetricCard } from '@/components/ui/metric_card';

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
    <div className="p-8 max-w-5xl">
      <PageHeader icon="⚙️" title="Kontenplan & Training" subtitle="Kontenplan bearbeiten, Modell trainieren" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Genauigkeit" value={classifyInfo?.model_accuracy ? `${(classifyInfo.model_accuracy * 100).toFixed(0)}%` : '—'} accent="blue" />
        <MetricCard title="Konten" value={konten.length} accent="green" />
        <MetricCard title="Gedächtnis" value={classifyInfo?.memory_count || 0} accent="amber" />
        <MetricCard title="Korrekturen" value={classifyInfo?.correction_count || 0} accent="gray" />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        {(['kontenplan', 'training'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === t ? 'border-brand-600 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}>
            {t === 'kontenplan' ? 'Kontenplan' : 'Training'}
          </button>
        ))}
      </div>

      {tab === 'kontenplan' && (
        <>
          <div className="flex gap-3 mb-4">
            <input
              type="text" placeholder="Suchen..." value={search} onChange={e => setSearch(e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
            <div className="flex-1" />
            <button onClick={() => setKonten(prev => [...prev, { konto: '', bezeichnung: '' }])} className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              + Konto hinzufügen
            </button>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 w-32">Konto-Nr.</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Bezeichnung</th>
                  <th className="w-12" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((k, i) => {
                  const realIdx = konten.indexOf(k);
                  return (
                    <tr key={i} className="border-b border-gray-100 hover:bg-gray-50/50">
                      <td className="px-4 py-2">
                        <input value={k.konto} onChange={e => updateKonto(realIdx, 'konto', e.target.value)}
                          className="w-full bg-transparent font-mono text-gray-900 focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5" />
                      </td>
                      <td className="px-4 py-2">
                        <input value={k.bezeichnung} onChange={e => updateKonto(realIdx, 'bezeichnung', e.target.value)}
                          className="w-full bg-transparent text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand-500/30 rounded px-1 py-0.5" />
                      </td>
                      <td className="px-2">
                        <button onClick={() => setKonten(prev => prev.filter((_, j) => j !== realIdx))} className="text-gray-300 hover:text-red-500 transition-colors">✕</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex gap-3">
            <button onClick={handleSave} disabled={saving}
              className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 shadow-sm transition-colors">
              {saving ? 'Speichert...' : '💾 Kontenplan speichern'}
            </button>
          </div>
        </>
      )}

      {tab === 'training' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-semibold text-gray-900 mb-2">Modell trainieren</h3>
          <p className="text-sm text-gray-500 mb-4">
            {classifyInfo?.correction_count ? `${classifyInfo.correction_count} Korrekturen verfügbar zum Trainieren.` : 'Noch keine Korrekturen vorhanden.'}
          </p>
          <button onClick={handleTrain} disabled={training}
            className="px-5 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 shadow-sm transition-colors">
            {training ? 'Trainiert...' : '🚀 Jetzt trainieren'}
          </button>
          {trainResult && (
            <div className={`mt-4 p-3 rounded-lg text-sm ${trainResult.startsWith('Fehler') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
              {trainResult}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
