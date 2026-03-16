"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import {
  Brain,
  Upload,
  Database,
  Eye,
  Cpu,
  CheckCircle,
  AlertTriangle,
  Loader2,
  FileSpreadsheet,
  Trash2,
  BarChart3,
  Download,
  Search,
  Shield,
  Zap,
  ChevronDown,
  ChevronUp,
  TestTube,
  BookOpen,
  RotateCcw,
  Package,
  Info,
  XCircle,
  ArrowRight,
  Sparkles,
  HardDrive,
  Clock,
  TrendingUp,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────
interface ModelInfo {
  has_model: boolean;
  model_accuracy: number;
  train_accuracy: number;
  total_samples: number;
  classes: number;
  memory_count: number;
  correction_count: number;
  trained_at: string;
  sklearn_version: string;
  model_size_kb: number;
  memory_size_kb: number;
}

interface VisionStatus {
  available: boolean;
  model_name: string | null;
  model_count: number;
  is_cloud: boolean;
}

interface ClassifyResult {
  source: string;
  kt_soll: string;
  kt_soll_name: string;
  kt_haben: string;
  kt_haben_name: string;
  mwst_code: string;
  mwst_pct: number;
  confidence: number;
  top_predictions?: { klass: string; name: string; probability: number }[];
}

interface MemoryEntry {
  lookup_key: string;
  beschreibung: string;
  kt_soll: string;
  kt_haben: string;
  mwst_code: string;
  mwst_pct: number;
}

interface ImportResult {
  imported: number;
  memory_entries: number;
  training?: {
    total_samples: number;
    classes: number;
    cv_accuracy: number | null;
    train_accuracy: number;
  };
}

interface TrainingData {
  konto_soll: string;
  bezeichnung: string;
  anzahl: number;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function accuracyColor(acc: number) {
  if (acc >= 0.85) return { text: "text-emerald-600", bg: "bg-emerald-500", ring: "ring-emerald-200" };
  if (acc >= 0.6) return { text: "text-amber-600", bg: "bg-amber-500", ring: "ring-amber-200" };
  return { text: "text-red-600", bg: "bg-red-500", ring: "ring-red-200" };
}

function formatDate(iso: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-CH", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
  accent = "text-gray-900",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">{label}</span>
      </div>
      <div className={`text-3xl font-extrabold tabular-nums ${accent}`}>{value}</div>
      <div className="text-xs text-gray-400 mt-1">{sub}</div>
    </div>
  );
}

function PipelineStep({ num, label, desc, colorClass }: { num: number; label: string; desc: string; colorClass: string }) {
  return (
    <div className={`flex-1 rounded-xl px-4 py-3 ${colorClass}`}>
      <div className="text-[11px] font-bold opacity-60">Stufe {num}</div>
      <div className="font-semibold text-sm mt-0.5">{label}</div>
      <div className="text-xs opacity-70 mt-0.5">{desc}</div>
    </div>
  );
}

function SystemStatusBadge({ hasModel, hasVision }: { hasModel: boolean; hasVision: boolean }) {
  if (hasModel && hasVision) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-medium">
        <CheckCircle className="w-4 h-4" />
        Buchhaltung Modell vollständig — Vision + ML aktiv
      </div>
    );
  }
  if (hasModel || hasVision) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-sm font-medium">
        <AlertTriangle className="w-4 h-4" />
        Teilweise aktiv — {hasModel ? "ML bereit, Vision fehlt" : "Vision bereit, ML fehlt"}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm font-medium">
      <XCircle className="w-4 h-4" />
      Nicht konfiguriert — Modell trainieren & Vision installieren
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ModellPage() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [vision, setVision] = useState<VisionStatus>({ available: false, model_name: null, model_count: 0, is_cloud: false });
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [replaceData, setReplaceData] = useState(false);
  const [activeTab, setActiveTab] = useState<"test" | "top" | "memory" | "retrain">("test");
  const [testInput, setTestInput] = useState("");
  const [testResult, setTestResult] = useState<ClassifyResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [memoryEntries, setMemoryEntries] = useState<MemoryEntry[]>([]);
  const [memoryFilter, setMemoryFilter] = useState("");
  const [topClasses, setTopClasses] = useState<TrainingData[]>([]);
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [dangerConfirm, setDangerConfirm] = useState<string | null>(null);

  const fetchInfo = useCallback(async () => {
    try {
      const [infoRes, visionRes] = await Promise.allSettled([
        api.get("/api/classify/info"),
        api.get("/api/scanner/vision-status")
      ]);
      if (infoRes.status === "fulfilled") setInfo(infoRes.value.data);
      if (visionRes.status === "fulfilled") setVision(visionRes.value.data);
    } catch {
      toast.error("Modell-Info konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchInfo(); }, [fetchInfo]);

  const handleTrain = async () => {
    setTraining(true);
    try {
      const res = await api.post("/api/classify/train");
      toast.success(
        `Modell trainiert! ${res.data.total_samples} Samples, ${((res.data.cv_accuracy || 0) * 100).toFixed(1)}% Genauigkeit`
      );
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Training fehlgeschlagen");
    } finally {
      setTraining(false);
    }
  };

  const handleTest = async () => {
    if (!testInput.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await api.post("/api/classify/predict", { beschreibung: testInput, betrag: 100 });
      setTestResult(res.data);
    } catch {
      toast.error("Klassifizierung fehlgeschlagen");
    } finally {
      setTestLoading(false);
    }
  };

  const fetchMemory = async () => {
    const res = await api.get("/api/classify/memory");
    setMemoryEntries(res.data.entries);
  };

  const fetchTopClasses = async () => {
    const res = await api.get("/api/classify/top-classes");
    setTopClasses(res.data);
  };

  useEffect(() => {
    if (activeTab === "memory") fetchMemory();
    if (activeTab === "top") fetchTopClasses();
  }, [activeTab]);

  const handleDangerAction = async (action: "memory" | "corrections" | "model") => {
    try {
      await api.delete(`/api/classify/${action}`);
      toast.success(
        action === "memory" ? "Gedächtnis gelöscht" :
        action === "corrections" ? "Korrekturen gelöscht" : "ML-Modell gelöscht"
      );
      setDangerConfirm(null);
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Aktion fehlgeschlagen");
    }
  };

  const handleDownload = async (type: "bundle" | "model" | "memory") => {
    try {
      const res = await api.get(`/api/classify/download/${type}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      const ext = type === "bundle" ? "zip" : type === "model" ? "pkl" : "json";
      a.href = url;
      a.download = `buchhaltung_${type}_${new Date().toISOString().slice(0, 16).replace(/[:-]/g, "")}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download fehlgeschlagen");
    }
  };

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (![".xls", ".xlsx", ".csv"].includes(ext)) {
      toast.error("Nur XLS, XLSX oder CSV Dateien erlaubt");
      return;
    }
    setImporting(true);
    setImportResult(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post(
        `/api/import/banana?replace=${replaceData}&also_memory=true&auto_train=true`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setImportResult(res.data);
      toast.success(`${res.data.imported} Buchungen importiert & Modell trainiert!`);
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Import fehlgeschlagen");
    } finally {
      setImporting(false);
    }
  }, [replaceData, fetchInfo]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.ms-excel": [".xls"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "text/csv": [".csv"],
    },
    maxFiles: 1,
    disabled: importing,
  });

  // Upload model bundle
  const handleUploadBundle = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post("/api/classify/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Modell wiederhergestellt!");
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Upload fehlgeschlagen");
    }
  };

  const {
    getRootProps: getRestoreProps,
    getInputProps: getRestoreInputProps,
  } = useDropzone({
    onDrop: (files) => files[0] && handleUploadBundle(files[0]),
    accept: {
      "application/zip": [".zip"],
      "application/octet-stream": [".pkl"],
      "application/json": [".json"],
    },
    maxFiles: 1,
  });

  const acc = info?.model_accuracy ?? 0;
  const accColors = accuracyColor(acc);
  const filteredMemory = memoryEntries.filter(e =>
    !memoryFilter || (e.lookup_key ?? "").toLowerCase().includes(memoryFilter.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-80 gap-3">
        <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
        <span className="text-sm text-gray-400">Modell wird geladen…</span>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-100">
              <Brain className="w-6 h-6 text-purple-600" />
            </div>
            Modell Manager
          </h1>
          <p className="text-gray-500 mt-1.5 text-sm">
            Buchhaltung ML-Modell verwalten, trainieren & inspizieren
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleDownload("bundle")}
            disabled={!info?.has_model && (info?.memory_count ?? 0) === 0}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-gray-200 rounded-xl hover:bg-gray-50 disabled:opacity-40 transition-all"
          >
            <Download className="w-4 h-4" />
            Exportieren
          </button>
          <button
            onClick={handleTrain}
            disabled={training || (info?.total_samples ?? 0) < 5}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50 transition-all shadow-sm shadow-purple-200"
          >
            {training ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {training ? "Trainiert…" : "Modell trainieren"}
          </button>
        </div>
      </div>

      {/* ── System Status ─────────────────────────────────────────────── */}
      <SystemStatusBadge hasModel={info?.has_model ?? false} hasVision={vision.available} />

      {/* ── Stat Cards ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          icon={<Cpu className="w-5 h-5 text-purple-500" />}
          label="Genauigkeit"
          value={info?.has_model ? `${(acc * 100).toFixed(1)}%` : "—"}
          sub={info?.has_model ? "Cross-Validation" : "Nicht trainiert"}
          accent={info?.has_model ? accColors.text : "text-gray-300"}
        />
        <StatCard
          icon={<Database className="w-5 h-5 text-blue-500" />}
          label="Samples"
          value={String(info?.total_samples ?? 0)}
          sub={`${info?.classes ?? 0} Kontenklassen`}
        />
        <StatCard
          icon={<Brain className="w-5 h-5 text-emerald-500" />}
          label="Gedächtnis"
          value={String(info?.memory_count ?? 0)}
          sub="Exakte Treffer"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-orange-500" />}
          label="Korrekturen"
          value={String(info?.correction_count ?? 0)}
          sub="Verfügbar"
        />
        <StatCard
          icon={<Eye className="w-5 h-5 text-indigo-500" />}
          label="Vision"
          value={vision.available ? (vision.is_cloud ? "Cloud" : "Lokal") : "—"}
          sub={vision.model_name ?? "Nicht verbunden"}
          accent={vision.available ? "text-indigo-600" : "text-gray-300"}
        />
      </div>

      {/* ── Accuracy Bar ──────────────────────────────────────────────── */}
      {info?.has_model && (
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="flex justify-between items-center mb-3">
            <div>
              <span className="text-sm font-semibold text-gray-700">Modell-Genauigkeit</span>
              {info.train_accuracy > 0 && acc > 0 && info.train_accuracy - acc > 0.15 && (
                <span className="ml-3 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                  ⚠ Overfit-Warnung
                </span>
              )}
            </div>
            <span className={`text-2xl font-extrabold tabular-nums ${accColors.text}`}>
              {(acc * 100).toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${accColors.bg}`}
              style={{ width: `${Math.min(acc * 100, 100)}%` }}
            />
          </div>
          <div className="flex justify-between mt-3 text-xs text-gray-400">
            <span>{info.total_samples} Buchungen · {info.classes} Klassen</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(info.trained_at)}
            </span>
          </div>
        </div>
      )}

      {/* ── Inspect Tabs ──────────────────────────────────────────────── */}
      {info?.has_model && (
        <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
          <div className="flex border-b border-gray-100">
            {[
              { key: "test", icon: TestTube, label: "Testen" },
              { key: "top", icon: BarChart3, label: "Top-Konten" },
              { key: "memory", icon: Brain, label: "Gedächtnis" },
              { key: "retrain", icon: RotateCcw, label: "Neu trainieren" },
            ].map(({ key, icon: Icon, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key as typeof activeTab)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3.5 text-sm font-medium transition-all ${
                  activeTab === key
                    ? "text-purple-600 border-b-2 border-purple-500 bg-purple-50/50"
                    : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>

          <div className="p-6">
            {/* Test Tab */}
            {activeTab === "test" && (
              <div className="space-y-5">
                <p className="text-sm text-gray-500">
                  Geben Sie eine Beschreibung ein und sehen Sie, wie das Modell klassifiziert.
                </p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleTest()}
                    placeholder="z.B. Migros Zürich Lebensmittel"
                    className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
                  />
                  <button
                    onClick={handleTest}
                    disabled={testLoading || !testInput.trim()}
                    className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white text-sm font-medium rounded-xl hover:bg-purple-700 disabled:opacity-50 transition-all"
                  >
                    {testLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    Testen
                  </button>
                </div>

                {testResult && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="rounded-xl bg-gray-50 p-4">
                        <div className="text-[11px] font-semibold text-gray-400 uppercase mb-1">Quelle</div>
                        <div className="text-lg font-bold">
                          {testResult.source === "Gedächtnis" ? "🧠" : testResult.source === "ML" ? "🤖" : "📋"}{" "}
                          {testResult.source}
                        </div>
                      </div>
                      <div className="rounded-xl bg-gray-50 p-4">
                        <div className="text-[11px] font-semibold text-gray-400 uppercase mb-1">KtSoll</div>
                        <div className="text-lg font-bold">{testResult.kt_soll}</div>
                        <div className="text-xs text-gray-500">{testResult.kt_soll_name}</div>
                      </div>
                      <div className="rounded-xl bg-gray-50 p-4">
                        <div className="text-[11px] font-semibold text-gray-400 uppercase mb-1">Konfidenz</div>
                        <div className={`text-lg font-bold ${accuracyColor(testResult.confidence).text}`}>
                          {(testResult.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-6 text-sm text-gray-600">
                      <span><strong>KtHaben:</strong> {testResult.kt_haben} ({testResult.kt_haben_name})</span>
                      {testResult.mwst_code && (
                        <span><strong>MwSt:</strong> {testResult.mwst_code} / {testResult.mwst_pct}%</span>
                      )}
                    </div>

                    {testResult.top_predictions && testResult.top_predictions.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-400 uppercase mb-3">Top 5 ML-Vorhersagen</h4>
                        <div className="space-y-2">
                          {testResult.top_predictions.map((pred) => (
                            <div key={pred.klass} className="flex items-center gap-3">
                              <code className="text-xs bg-gray-100 px-2 py-0.5 rounded font-mono w-14 text-center">
                                {pred.klass}
                              </code>
                              <span className="text-sm text-gray-600 w-40 truncate">{pred.name}</span>
                              <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                                <div
                                  className="h-full bg-purple-500 rounded-full transition-all"
                                  style={{ width: `${pred.probability * 100}%` }}
                                />
                              </div>
                              <span className="text-xs font-semibold tabular-nums w-12 text-right">
                                {(pred.probability * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Top Classes Tab */}
            {activeTab === "top" && (
              <div>
                <p className="text-sm text-gray-500 mb-4">Häufigste Kontoklassen im Trainingsset</p>
                {topClasses.length > 0 ? (
                  <div className="overflow-hidden rounded-xl border border-gray-100">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 text-left">
                          <th className="px-4 py-2.5 font-semibold text-gray-600">KontoSoll</th>
                          <th className="px-4 py-2.5 font-semibold text-gray-600">Bezeichnung</th>
                          <th className="px-4 py-2.5 font-semibold text-gray-600 text-right">Anzahl</th>
                          <th className="px-4 py-2.5 font-semibold text-gray-600 w-40">Verteilung</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topClasses.map((cls, i) => {
                          const maxCount = topClasses[0]?.anzahl ?? 1;
                          return (
                            <tr key={cls.konto_soll} className={i % 2 === 0 ? "" : "bg-gray-50/50"}>
                              <td className="px-4 py-2.5 font-mono font-medium">{cls.konto_soll}</td>
                              <td className="px-4 py-2.5 text-gray-600">{cls.bezeichnung}</td>
                              <td className="px-4 py-2.5 text-right tabular-nums font-medium">{cls.anzahl}</td>
                              <td className="px-4 py-2.5">
                                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                                  <div
                                    className="h-full bg-blue-500 rounded-full"
                                    style={{ width: `${(cls.anzahl / maxCount) * 100}%` }}
                                  />
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-400">
                    <Database className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    Keine Trainingsdaten vorhanden
                  </div>
                )}
              </div>
            )}

            {/* Memory Tab */}
            {activeTab === "memory" && (
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={memoryFilter}
                      onChange={(e) => setMemoryFilter(e.target.value)}
                      placeholder="Gedächtnis durchsuchen…"
                      className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-200 transition-all"
                    />
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap">
                    {filteredMemory.length} / {memoryEntries.length} Einträge
                  </span>
                </div>
                {filteredMemory.length > 0 ? (
                  <div className="overflow-hidden rounded-xl border border-gray-100 max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-white">
                        <tr className="bg-gray-50 text-left">
                          <th className="px-4 py-2.5 font-semibold text-gray-600">Beschreibung</th>
                          <th className="px-4 py-2.5 font-semibold text-gray-600">KtSoll</th>
                          <th className="px-4 py-2.5 font-semibold text-gray-600">KtHaben</th>
                          <th className="px-4 py-2.5 font-semibold text-gray-600">MwSt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredMemory.map((entry, i) => (
                          <tr key={entry.lookup_key} className={i % 2 === 0 ? "" : "bg-gray-50/50"}>
                            <td className="px-4 py-2 text-gray-700 max-w-xs truncate">{entry.lookup_key}</td>
                            <td className="px-4 py-2 font-mono">{entry.kt_soll}</td>
                            <td className="px-4 py-2 font-mono">{entry.kt_haben}</td>
                            <td className="px-4 py-2 text-gray-500">{entry.mwst_code || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-400">
                    <Brain className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    {memoryEntries.length === 0 ? "Gedächtnis ist leer" : "Keine Treffer"}
                  </div>
                )}
              </div>
            )}

            {/* Retrain Tab */}
            {activeTab === "retrain" && (
              <div className="space-y-4">
                {(info?.correction_count ?? 0) > 0 ? (
                  <>
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-blue-50 border border-blue-200 text-blue-700">
                      <Info className="w-5 h-5 shrink-0" />
                      <span className="text-sm">
                        <strong>{info?.correction_count} Korrekturen</strong> seit letztem Training verfügbar.
                        Neu trainieren verbessert die Genauigkeit.
                      </span>
                    </div>
                    <button
                      onClick={handleTrain}
                      disabled={training}
                      className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white text-sm font-medium rounded-xl hover:bg-purple-700 disabled:opacity-50 transition-all"
                    >
                      {training ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                      Jetzt neu trainieren
                    </button>
                  </>
                ) : (
                  <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700">
                    <CheckCircle className="w-5 h-5 shrink-0" />
                    <span className="text-sm">Modell ist aktuell — keine neuen Korrekturen vorhanden.</span>
                  </div>
                )}
                <p className="text-xs text-gray-400 pt-2">
                  💡 Je mehr Rechnungen Sie scannen und bestätigen, desto besser wird das Modell.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Import Section ────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-1">
          <FileSpreadsheet className="w-5 h-5 text-green-600" />
          Banana Import
        </h2>
        <p className="text-sm text-gray-500 mb-5">
          Laden Sie Ihre <strong>Doppelte Buchhaltung mit MWST</strong> Datei hoch — Buchungen werden importiert und das Modell automatisch trainiert.
        </p>

        <label className="flex items-center gap-2 text-sm cursor-pointer mb-4">
          <input
            type="checkbox"
            checked={replaceData}
            onChange={(e) => setReplaceData(e.target.checked)}
            className="rounded border-gray-300 text-purple-600 focus:ring-purple-200"
          />
          <Trash2 className="w-3.5 h-3.5 text-red-400" />
          Bestehende Trainingsdaten ersetzen
        </label>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
            isDragActive
              ? "border-green-400 bg-green-50/80"
              : importing
              ? "border-gray-200 bg-gray-50"
              : "border-gray-200 hover:border-purple-300 hover:bg-purple-50/30"
          }`}
        >
          <input {...getInputProps()} />
          {importing ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
              <p className="text-purple-600 font-medium">Importiert & trainiert…</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-10 h-10 text-gray-300" />
              <p className="text-gray-600 font-medium">XLS / XLSX / CSV hierher ziehen oder klicken</p>
              <p className="text-xs text-gray-400">Banana Format: Buchungen mit Beschreibung, KtSoll, KtHaben, MwSt</p>
            </div>
          )}
        </div>

        {importResult && (
          <div className="mt-4 p-4 rounded-xl bg-emerald-50 border border-emerald-200">
            <h3 className="font-medium text-emerald-800 flex items-center gap-2 text-sm">
              <CheckCircle className="w-4 h-4" /> Import erfolgreich
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
              <div className="text-center">
                <div className="text-xl font-bold text-emerald-700">{importResult.imported}</div>
                <div className="text-xs text-emerald-600">Buchungen</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-emerald-700">{importResult.memory_entries}</div>
                <div className="text-xs text-emerald-600">Gedächtnis</div>
              </div>
              {importResult.training && (
                <>
                  <div className="text-center">
                    <div className="text-xl font-bold text-emerald-700">
                      {((importResult.training.cv_accuracy ?? 0) * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-emerald-600">Genauigkeit</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-emerald-700">{importResult.training.classes}</div>
                    <div className="text-xs text-emerald-600">Klassen</div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Download & Upload ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h3 className="font-semibold flex items-center gap-2 mb-3">
            <Download className="w-4 h-4 text-blue-500" />
            Modell exportieren
          </h3>
          <p className="text-xs text-gray-500 mb-4">Sicherung inkl. ML-Modell, Gedächtnis, Kontenplan & Korrekturen</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleDownload("bundle")}
              disabled={!info?.has_model && (info?.memory_count ?? 0) === 0}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-40 transition-all"
            >
              <Package className="w-4 h-4" />
              Komplettpaket .zip
            </button>
            <button
              onClick={() => handleDownload("model")}
              disabled={!info?.has_model}
              className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-200 rounded-xl hover:bg-gray-50 disabled:opacity-40 transition-all"
            >
              Nur ML .pkl
            </button>
            <button
              onClick={() => handleDownload("memory")}
              disabled={(info?.memory_count ?? 0) === 0}
              className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-200 rounded-xl hover:bg-gray-50 disabled:opacity-40 transition-all"
            >
              Nur Gedächtnis .json
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h3 className="font-semibold flex items-center gap-2 mb-3">
            <Upload className="w-4 h-4 text-green-500" />
            Modell importieren
          </h3>
          <p className="text-xs text-gray-500 mb-4">Ein zuvor gesichertes Modell-Paket wiederherstellen</p>
          <div
            {...getRestoreProps()}
            className="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer hover:border-purple-300 hover:bg-purple-50/30 transition-all"
          >
            <input {...getRestoreInputProps()} />
            <Upload className="w-6 h-6 text-gray-300 mx-auto mb-1" />
            <p className="text-xs text-gray-500">.zip / .pkl / .json hierher ziehen</p>
          </div>
        </div>
      </div>

      {/* ── Pipeline ──────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <button
          onClick={() => setShowHowItWorks(!showHowItWorks)}
          className="w-full flex items-center justify-between"
        >
          <h3 className="font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            Klassifizierungs-Pipeline
          </h3>
          {showHowItWorks ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </button>

        <div className="flex items-center gap-2 mt-4">
          <PipelineStep num={1} label="Gedächtnis" desc="Exakte Treffer" colorClass="bg-emerald-50 text-emerald-700" />
          <ArrowRight className="w-4 h-4 text-gray-300 shrink-0" />
          <PipelineStep num={2} label="ML-Modell" desc="TF-IDF + LogReg" colorClass="bg-purple-50 text-purple-700" />
          <ArrowRight className="w-4 h-4 text-gray-300 shrink-0" />
          <PipelineStep num={3} label="Regeln" desc="Keyword-Fallback" colorClass="bg-orange-50 text-orange-700" />
        </div>

        {showHowItWorks && (
          <div className="mt-5 p-4 rounded-xl bg-gray-50 text-sm text-gray-600 space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
            <p><strong>So lernt das System:</strong></p>
            <ol className="list-decimal list-inside space-y-1 text-gray-500">
              <li>Sie scannen eine Rechnung → Vision liest Lieferant, Datum, Betrag</li>
              <li>ML klassifiziert → schlägt Konten vor</li>
              <li>Sie bestätigen oder korrigieren</li>
              <li>System speichert im Gedächtnis → beim nächsten Mal sofort korrekt</li>
            </ol>
          </div>
        )}
      </div>

      {/* ── Danger Zone ───────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-red-100 bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-red-600 flex items-center gap-2 mb-1">
          <Shield className="w-4 h-4" />
          Gefahrenzone
        </h3>
        <p className="text-xs text-gray-400 mb-4">Diese Aktionen können nicht rückgängig gemacht werden — sichern Sie zuerst Ihr Modell.</p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { key: "memory", label: "Gedächtnis leeren", icon: Brain, count: info?.memory_count },
            { key: "corrections", label: "Korrekturen leeren", icon: TrendingUp, count: info?.correction_count },
            { key: "model", label: "ML-Modell löschen", icon: Cpu, count: info?.has_model ? 1 : 0 },
          ].map(({ key, label, icon: Icon, count }) => (
            <div key={key}>
              {dangerConfirm === key ? (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleDangerAction(key as any)}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-2.5 text-sm font-medium bg-red-600 text-white rounded-xl hover:bg-red-700 transition-all"
                  >
                    Bestätigen
                  </button>
                  <button
                    onClick={() => setDangerConfirm(null)}
                    className="px-3 py-2.5 text-sm border border-gray-200 rounded-xl hover:bg-gray-50 transition-all"
                  >
                    Abbrechen
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setDangerConfirm(key)}
                  disabled={!count}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium border border-red-200 text-red-600 rounded-xl hover:bg-red-50 disabled:opacity-30 transition-all"
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
