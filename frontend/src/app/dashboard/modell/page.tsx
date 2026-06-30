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
  Clock,
  TrendingUp,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

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

function accuracyTone(acc: number): "success" | "warning" | "danger" {
  if (acc >= 0.85) return "success";
  if (acc >= 0.6) return "warning";
  return "danger";
}

function accuracyBarClass(acc: number) {
  if (acc >= 0.85) return "bg-success";
  if (acc >= 0.6) return "bg-warning";
  return "bg-destructive";
}

function accuracyTextClass(acc: number) {
  if (acc >= 0.85) return "text-success";
  if (acc >= 0.6) return "text-warning";
  return "text-destructive";
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
  valueClass = "text-foreground",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{label}</span>
      </div>
      <div className={cn("text-2xl font-extrabold tabular-nums", valueClass)}>{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}

function PipelineStep({ num, label, desc, tone }: { num: number; label: string; desc: string; tone: "success" | "brand" | "warning" }) {
  const styles = {
    success: "bg-success/10 text-success",
    brand: "bg-brand-500/12 text-brand-600 dark:text-brand-300",
    warning: "bg-warning/12 text-warning",
  }[tone];
  return (
    <div className={cn("flex-1 rounded-xl px-4 py-3", styles)}>
      <div className="text-[11px] font-bold opacity-60">Stufe {num}</div>
      <div className="font-semibold text-sm mt-0.5">{label}</div>
      <div className="text-xs opacity-70 mt-0.5">{desc}</div>
    </div>
  );
}

function SystemStatusBadge({ hasModel, hasVision }: { hasModel: boolean; hasVision: boolean }) {
  if (hasModel && hasVision) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-success/10 border border-success/25 text-success text-sm font-medium">
        <CheckCircle className="w-4 h-4" />
        Buchhaltung Modell vollständig — Vision + ML aktiv
      </div>
    );
  }
  if (hasModel || hasVision) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-warning/10 border border-warning/25 text-warning text-sm font-medium">
        <AlertTriangle className="w-4 h-4" />
        Teilweise aktiv — {hasModel ? "ML bereit, Vision fehlt" : "Vision bereit, ML fehlt"}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-destructive/10 border border-destructive/25 text-destructive text-sm font-medium">
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
  const filteredMemory = memoryEntries.filter(e =>
    !memoryFilter || (e.lookup_key ?? "").toLowerCase().includes(memoryFilter.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-80 gap-3">
        <Loader2 className="w-10 h-10 animate-spin text-brand-600 dark:text-brand-300" />
        <span className="text-sm text-muted-foreground">Modell wird geladen…</span>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <PageHeader
        icon={Brain}
        title="Modell Manager"
        subtitle="Buchhaltung ML-Modell verwalten, trainieren & inspizieren"
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => handleDownload("bundle")}
              disabled={!info?.has_model && (info?.memory_count ?? 0) === 0}
              icon={<Download className="w-4 h-4" />}
            >
              Exportieren
            </Button>
            <Button
              variant="primary"
              onClick={handleTrain}
              disabled={training || (info?.total_samples ?? 0) < 5}
              loading={training}
              icon={<Sparkles className="w-4 h-4" />}
            >
              {training ? "Trainiert…" : "Modell trainieren"}
            </Button>
          </div>
        }
      />

      {/* ── System Status ─────────────────────────────────────────────── */}
      <SystemStatusBadge hasModel={info?.has_model ?? false} hasVision={vision.available} />

      {/* ── Stat Cards ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          icon={<Cpu className="w-5 h-5 text-brand-600 dark:text-brand-300" />}
          label="Genauigkeit"
          value={info?.has_model ? `${(acc * 100).toFixed(1)}%` : "—"}
          sub={info?.has_model ? "Cross-Validation" : "Nicht trainiert"}
          valueClass={info?.has_model ? accuracyTextClass(acc) : "text-muted-foreground"}
        />
        <StatCard
          icon={<Database className="w-5 h-5 text-info" />}
          label="Samples"
          value={String(info?.total_samples ?? 0)}
          sub={`${info?.classes ?? 0} Kontenklassen`}
        />
        <StatCard
          icon={<Brain className="w-5 h-5 text-success" />}
          label="Gedächtnis"
          value={String(info?.memory_count ?? 0)}
          sub="Exakte Treffer"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-warning" />}
          label="Korrekturen"
          value={String(info?.correction_count ?? 0)}
          sub="Verfügbar"
        />
        <StatCard
          icon={<Eye className="w-5 h-5 text-brand-600 dark:text-brand-300" />}
          label="Vision"
          value={vision.available ? (vision.is_cloud ? "Cloud" : "Lokal") : "—"}
          sub={vision.model_name ?? "Nicht verbunden"}
          valueClass={vision.available ? "text-brand-600 dark:text-brand-300" : "text-muted-foreground"}
        />
      </div>

      {/* ── Accuracy Bar ──────────────────────────────────────────────── */}
      {info?.has_model && (
        <Card>
          <CardContent className="pt-5">
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-foreground">Modell-Genauigkeit</span>
                {info.train_accuracy > 0 && acc > 0 && info.train_accuracy - acc > 0.15 && (
                  <Badge tone="warning" dot>Overfit-Warnung</Badge>
                )}
              </div>
              <span className={cn("text-xl font-extrabold tabular-nums", accuracyTextClass(acc))}>
                {(acc * 100).toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
              <div
                className={cn("h-full rounded-full transition-all duration-1000 ease-out", accuracyBarClass(acc))}
                style={{ width: `${Math.min(acc * 100, 100)}%` }}
              />
            </div>
            <div className="flex justify-between mt-3 text-xs text-muted-foreground">
              <span className="tabular-nums">{info.total_samples} Buchungen · {info.classes} Klassen</span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDate(info.trained_at)}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Inspect Tabs ──────────────────────────────────────────────── */}
      {info?.has_model && (
        <Card>
          <div className="flex border-b border-border">
            {[
              { key: "test", icon: TestTube, label: "Testen" },
              { key: "top", icon: BarChart3, label: "Top-Konten" },
              { key: "memory", icon: Brain, label: "Gedächtnis" },
              { key: "retrain", icon: RotateCcw, label: "Neu trainieren" },
            ].map(({ key, icon: Icon, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key as typeof activeTab)}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 px-4 py-3.5 text-sm font-medium transition-all",
                  activeTab === key
                    ? "text-brand-600 dark:text-brand-300 border-b-2 border-brand-600 dark:border-brand-300 bg-brand-500/6"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>

          <CardContent className="pt-5">
            {/* Test Tab */}
            {activeTab === "test" && (
              <div className="space-y-5">
                <p className="text-sm text-muted-foreground">
                  Geben Sie eine Beschreibung ein und sehen Sie, wie das Modell klassifiziert.
                </p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleTest()}
                    placeholder="z.B. Migros Zürich Lebensmittel"
                    className="flex-1 px-4 py-2.5 border border-input rounded-xl text-sm text-foreground bg-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring transition-all"
                  />
                  <Button
                    variant="primary"
                    onClick={handleTest}
                    disabled={testLoading || !testInput.trim()}
                    loading={testLoading}
                    icon={<Search className="w-4 h-4" />}
                  >
                    Testen
                  </Button>
                </div>

                {testResult && (
                  <div className="space-y-4 animate-fade-in">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="rounded-xl bg-muted p-4">
                        <div className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">Quelle</div>
                        <div className="text-base font-bold text-foreground">{testResult.source}</div>
                      </div>
                      <div className="rounded-xl bg-muted p-4">
                        <div className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">KtSoll</div>
                        <div className="text-base font-bold text-foreground">{testResult.kt_soll}</div>
                        <div className="text-xs text-muted-foreground">{testResult.kt_soll_name}</div>
                      </div>
                      <div className="rounded-xl bg-muted p-4">
                        <div className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">Konfidenz</div>
                        <div className={cn("text-base font-bold tabular-nums", accuracyTextClass(testResult.confidence))}>
                          {(testResult.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-6 text-sm text-muted-foreground">
                      <span><strong className="text-foreground">KtHaben:</strong> {testResult.kt_haben} ({testResult.kt_haben_name})</span>
                      {testResult.mwst_code && (
                        <span><strong className="text-foreground">MwSt:</strong> {testResult.mwst_code} / {testResult.mwst_pct}%</span>
                      )}
                    </div>

                    {testResult.top_predictions && testResult.top_predictions.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-3">Top 5 ML-Vorhersagen</h4>
                        <div className="space-y-2">
                          {testResult.top_predictions.map((pred) => (
                            <div key={pred.klass} className="flex items-center gap-3">
                              <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono w-14 text-center text-foreground">
                                {pred.klass}
                              </code>
                              <span className="text-sm text-muted-foreground w-40 truncate">{pred.name}</span>
                              <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                                <div
                                  className="h-full bg-brand-500 rounded-full transition-all"
                                  style={{ width: `${pred.probability * 100}%` }}
                                />
                              </div>
                              <span className="text-xs font-semibold tabular-nums w-12 text-right text-foreground">
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
                <p className="text-sm text-muted-foreground mb-4">Häufigste Kontoklassen im Trainingsset</p>
                {topClasses.length > 0 ? (
                  <div className="overflow-hidden rounded-xl border border-border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-muted text-left">
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground">KontoSoll</th>
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground">Bezeichnung</th>
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground text-right">Anzahl</th>
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground w-40">Verteilung</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topClasses.map((cls, i) => {
                          const maxCount = topClasses[0]?.anzahl ?? 1;
                          return (
                            <tr key={cls.konto_soll} className="border-t border-border hover:bg-accent transition-colors">
                              <td className="px-4 py-2.5 font-mono font-medium text-foreground">{cls.konto_soll}</td>
                              <td className="px-4 py-2.5 text-muted-foreground">{cls.bezeichnung}</td>
                              <td className="px-4 py-2.5 text-right tabular-nums font-medium text-foreground">{cls.anzahl}</td>
                              <td className="px-4 py-2.5">
                                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                                  <div
                                    className="h-full bg-brand-500 rounded-full"
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
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Database className="w-8 h-8 mb-2 opacity-40" />
                    <p className="text-sm">Keine Trainingsdaten vorhanden</p>
                  </div>
                )}
              </div>
            )}

            {/* Memory Tab */}
            {activeTab === "memory" && (
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <input
                      type="text"
                      value={memoryFilter}
                      onChange={(e) => setMemoryFilter(e.target.value)}
                      placeholder="Gedächtnis durchsuchen…"
                      className="w-full pl-9 pr-4 py-2 border border-input rounded-xl text-sm text-foreground bg-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 transition-all"
                    />
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
                    {filteredMemory.length} / {memoryEntries.length} Einträge
                  </span>
                </div>
                {filteredMemory.length > 0 ? (
                  <div className="overflow-hidden rounded-xl border border-border max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-card">
                        <tr className="bg-muted text-left border-b border-border">
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground">Beschreibung</th>
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground">KtSoll</th>
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground">KtHaben</th>
                          <th className="px-4 py-2.5 font-semibold text-muted-foreground">MwSt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredMemory.map((entry, i) => (
                          <tr key={entry.lookup_key} className="border-t border-border hover:bg-accent transition-colors">
                            <td className="px-4 py-2 text-foreground max-w-xs truncate">{entry.lookup_key}</td>
                            <td className="px-4 py-2 font-mono text-foreground">{entry.kt_soll}</td>
                            <td className="px-4 py-2 font-mono text-foreground">{entry.kt_haben}</td>
                            <td className="px-4 py-2 text-muted-foreground">{entry.mwst_code || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Brain className="w-8 h-8 mb-2 opacity-40" />
                    <p className="text-sm">{memoryEntries.length === 0 ? "Gedächtnis ist leer" : "Keine Treffer"}</p>
                  </div>
                )}
              </div>
            )}

            {/* Retrain Tab */}
            {activeTab === "retrain" && (
              <div className="space-y-4">
                {(info?.correction_count ?? 0) > 0 ? (
                  <>
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-info/10 border border-info/25 text-info">
                      <Info className="w-5 h-5 shrink-0" />
                      <span className="text-sm">
                        <strong>{info?.correction_count} Korrekturen</strong> seit letztem Training verfügbar.
                        Neu trainieren verbessert die Genauigkeit.
                      </span>
                    </div>
                    <Button
                      variant="primary"
                      onClick={handleTrain}
                      disabled={training}
                      loading={training}
                      icon={<RotateCcw className="w-4 h-4" />}
                    >
                      Jetzt neu trainieren
                    </Button>
                  </>
                ) : (
                  <div className="flex items-center gap-3 p-4 rounded-xl bg-success/10 border border-success/25 text-success">
                    <CheckCircle className="w-5 h-5 shrink-0" />
                    <span className="text-sm">Modell ist aktuell — keine neuen Korrekturen vorhanden.</span>
                  </div>
                )}
                <p className="text-xs text-muted-foreground pt-2">
                  Je mehr Rechnungen Sie scannen und bestätigen, desto besser wird das Modell.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Import Section ────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-success" />
            <CardTitle>Banana Import</CardTitle>
          </div>
          <CardDescription>
            Laden Sie Ihre <strong>Doppelte Buchhaltung mit MWST</strong> Datei hoch — Buchungen werden importiert und das Modell automatisch trainiert.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <label className="flex items-center gap-2 text-sm cursor-pointer mb-4">
            <input
              type="checkbox"
              checked={replaceData}
              onChange={(e) => setReplaceData(e.target.checked)}
              className="rounded border-input text-brand-600 focus:ring-brand-500/20"
            />
            <Trash2 className="w-3.5 h-3.5 text-destructive" />
            <span className="text-foreground">Bestehende Trainingsdaten ersetzen</span>
          </label>

          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all",
              isDragActive
                ? "border-success/60 bg-success/8"
                : importing
                ? "border-border bg-muted/30"
                : "border-border hover:border-brand-400 hover:bg-brand-500/6"
            )}
          >
            <input {...getInputProps()} />
            {importing ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="w-10 h-10 animate-spin text-brand-600 dark:text-brand-300" />
                <p className="text-brand-600 dark:text-brand-300 font-medium">Importiert & trainiert…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload className="w-10 h-10 text-muted-foreground/40" />
                <p className="text-foreground font-medium">XLS / XLSX / CSV hierher ziehen oder klicken</p>
                <p className="text-xs text-muted-foreground">Banana Format: Buchungen mit Beschreibung, KtSoll, KtHaben, MwSt</p>
              </div>
            )}
          </div>

          {importResult && (
            <div className="mt-4 p-4 rounded-xl bg-success/10 border border-success/25">
              <h3 className="font-medium text-success flex items-center gap-2 text-sm">
                <CheckCircle className="w-4 h-4" /> Import erfolgreich
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
                <div className="text-center">
                  <div className="text-xl font-bold text-success tabular-nums">{importResult.imported}</div>
                  <div className="text-xs text-muted-foreground">Buchungen</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-success tabular-nums">{importResult.memory_entries}</div>
                  <div className="text-xs text-muted-foreground">Gedächtnis</div>
                </div>
                {importResult.training && (
                  <>
                    <div className="text-center">
                      <div className="text-xl font-bold text-success tabular-nums">
                        {((importResult.training.cv_accuracy ?? 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground">Genauigkeit</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-bold text-success tabular-nums">{importResult.training.classes}</div>
                      <div className="text-xs text-muted-foreground">Klassen</div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Download & Upload ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Download className="w-4 h-4 text-info" />
              <CardTitle>Modell exportieren</CardTitle>
            </div>
            <CardDescription>Sicherung inkl. ML-Modell, Gedächtnis, Kontenplan & Korrekturen</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleDownload("bundle")}
                disabled={!info?.has_model && (info?.memory_count ?? 0) === 0}
                icon={<Package className="w-4 h-4" />}
              >
                Komplettpaket .zip
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDownload("model")}
                disabled={!info?.has_model}
              >
                Nur ML .pkl
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDownload("memory")}
                disabled={(info?.memory_count ?? 0) === 0}
              >
                Nur Gedächtnis .json
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Upload className="w-4 h-4 text-success" />
              <CardTitle>Modell importieren</CardTitle>
            </div>
            <CardDescription>Ein zuvor gesichertes Modell-Paket wiederherstellen</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              {...getRestoreProps()}
              className="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-500/6 transition-all"
            >
              <input {...getRestoreInputProps()} />
              <Upload className="w-6 h-6 text-muted-foreground/40 mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">.zip / .pkl / .json hierher ziehen</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Pipeline ──────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-5">
          <button
            onClick={() => setShowHowItWorks(!showHowItWorks)}
            className="w-full flex items-center justify-between"
          >
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Zap className="w-4 h-4 text-warning" />
              Klassifizierungs-Pipeline
            </h3>
            {showHowItWorks ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
          </button>

          <div className="flex items-center gap-2 mt-4">
            <PipelineStep num={1} label="Gedächtnis" desc="Exakte Treffer" tone="success" />
            <ArrowRight className="w-4 h-4 text-muted-foreground/40 shrink-0" />
            <PipelineStep num={2} label="ML-Modell" desc="TF-IDF + LogReg" tone="brand" />
            <ArrowRight className="w-4 h-4 text-muted-foreground/40 shrink-0" />
            <PipelineStep num={3} label="Regeln" desc="Keyword-Fallback" tone="warning" />
          </div>

          {showHowItWorks && (
            <div className="mt-5 p-4 rounded-xl bg-muted text-sm text-foreground space-y-2 animate-fade-in">
              <p><strong>So lernt das System:</strong></p>
              <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                <li>Sie scannen eine Rechnung → Vision liest Lieferant, Datum, Betrag</li>
                <li>ML klassifiziert → schlägt Konten vor</li>
                <li>Sie bestätigen oder korrigieren</li>
                <li>System speichert im Gedächtnis → beim nächsten Mal sofort korrekt</li>
              </ol>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Danger Zone ───────────────────────────────────────────────── */}
      <div className="rounded-xl border border-destructive/25 bg-card p-6 shadow-sm">
        <h3 className="font-semibold text-destructive flex items-center gap-2 mb-1">
          <Shield className="w-4 h-4" />
          Gefahrenzone
        </h3>
        <p className="text-xs text-muted-foreground mb-4">Diese Aktionen können nicht rückgängig gemacht werden — sichern Sie zuerst Ihr Modell.</p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { key: "memory", label: "Gedächtnis leeren", icon: Brain, count: info?.memory_count },
            { key: "corrections", label: "Korrekturen leeren", icon: TrendingUp, count: info?.correction_count },
            { key: "model", label: "ML-Modell löschen", icon: Cpu, count: info?.has_model ? 1 : 0 },
          ].map(({ key, label, icon: Icon, count }) => (
            <div key={key}>
              {dangerConfirm === key ? (
                <div className="flex gap-2">
                  <Button
                    variant="danger"
                    size="sm"
                    className="flex-1"
                    onClick={() => handleDangerAction(key as "memory" | "corrections" | "model")}
                  >
                    Bestätigen
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDangerConfirm(null)}
                  >
                    Abbrechen
                  </Button>
                </div>
              ) : (
                <Button
                  variant="danger"
                  size="sm"
                  className="w-full"
                  onClick={() => setDangerConfirm(key)}
                  disabled={!count}
                  icon={<Icon className="w-4 h-4" />}
                >
                  {label}
                </Button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
