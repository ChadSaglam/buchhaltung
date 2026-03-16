"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import api from "@/lib/api";
import {
  Camera, Loader2, CheckCircle, AlertTriangle, XCircle, Trash2, Download,
  Mail, ChevronDown, ChevronUp, Eye, Cpu, Lightbulb, FileText, Save,
  Calculator, Send, Zap, RotateCcw, List, Edit3, Plus, Brain, Search,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────
interface OllamaStatus {
  ok: boolean;
  error?: string;
  models?: { name: string }[];
  vision_models?: string[];
  best_vision?: string | null;
}

interface ExtractedInvoice {
  vendor: string;
  date: string;
  invoice_number: string;
  description: string;
  total_amount: number;
  vat_rate: number;
  line_items: { item: string; amount: number }[];
  kt_soll?: string;
  kt_haben?: string;
  mwst_code?: string;
  mwst_pct?: string;
  mwst_amount?: number;
  classification_confidence?: number;
  classification_source?: string;
}

interface PipelineInfo {
  steps: string[];
  error?: string;
}

interface ClassificationResult {
  kt_soll: string;
  kt_soll_name: string;
  kt_haben: string;
  kt_haben_name: string;
  mwst_code: string;
  mwst_pct: string;
  mwst_amount: number;
  confidence: number;
  source: string;
}

interface BuchungRow {
  nr: number;
  datum: string;
  beleg: string;
  rechnung: string;
  beschreibung: string;
  kt_soll: string;
  kt_haben: string;
  betrag: number;
  mwstcode: string;
  artbetrag: string;
  mwstpct: string;
  mwstchf: number | string;
  ks3: string;
}

const MWST_CODE_OPTIONS = ["", "V81", "M81", "I81", "V77", "M77", "I77", "V25", "M25", "I25", "I26"];
const MWST_PCT_OPTIONS = ["", "8.10", "7.70", "2.60", "2.50", "-8.10", "-7.70"];

// ── Helpers ──────────────────────────────────────────────────────────────────
function sourceIcon(source: string) {
  return source === "Gedächtnis" ? "🧠" : source === "ML" ? "🤖" : "📋";
}

function calcMwst(betrag: number, pct: string): number {
  if (!pct || !betrag) return 0;
  const p = Math.abs(parseFloat(pct));
  const val = (betrag * p) / (100 + p);
  return parseFloat(pct) < 0 ? -Math.round(val * 100) / 100 : Math.round(val * 100) / 100;
}

function modelDisplayName(name: string, visionModels: string[]): string {
  if (!name) return "Unbekanntes Modell";
  const isVision = visionModels.includes(name);
  const isCloud = name.endsWith(":cloud") || name.endsWith("-cloud");
  let label = name;
  if (isVision && isCloud) label = `⚡👁 ${name}`;
  else if (isVision) label = `👁 ${name}`;
  else if (isCloud) label = `⚡ ${name}`;
  return label;
}


// ── Small Reusable Components ────────────────────────────────────────────────
function FieldInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
      />
    </div>
  );
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all appearance-none"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt || "—"}</option>
        ))}
      </select>
    </div>
  );
}

// ── Invoice Card ─────────────────────────────────────────────────────────────
function InvoiceCard({
  file, selectedModel, onAddBooking,
}: {
  file: File; selectedModel: string; onAddBooking: (row: BuchungRow) => void;
}) {
  const [extracting, setExtracting] = useState(false);
  const [result, setResult] = useState<ExtractedInvoice | null>(null);
  const [pipelineInfo, setPipelineInfo] = useState<PipelineInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState("");
  const [elapsedSec, setElapsedSec] = useState(0);

  // Editable fields
  const [vendor, setVendor] = useState("");
  const [date, setDate] = useState("");
  const [invNr, setInvNr] = useState("");
  const [desc, setDesc] = useState("");
  const [total, setTotal] = useState(0);
  const [vatRate, setVatRate] = useState(0);
  const [ktSoll, setKtSoll] = useState("");
  const [ktHaben, setKtHaben] = useState("");
  const [mwstCode, setMwstCode] = useState("");
  const [mwstPct, setMwstPct] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [classSource, setClassSource] = useState("");
  const [showLineItems, setShowLineItems] = useState(false);
  const [added, setAdded] = useState(false);

  const extractedRef = useRef(false);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const extract = useCallback(async () => {
    setExtracting(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);
    if (selectedModel) formData.append("model", selectedModel);
    try {
      const res = await api.post("/api/scanner/extract", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 180000,
      });
      console.log("Extract response:", JSON.stringify(res.data));
      const data = res.data.data;
      const pipe = res.data.pipeline_info ?? null;
      setResult(data);
      setPipelineInfo(pipe);
      setVendor(data.vendor || "");
      setDate(data.date || "");
      setInvNr(data.invoice_number || "");
      setDesc(data.description || "");
      setTotal(data.total_amount || 0);
      setVatRate(data.vat_rate || 0);
      // Classification — snake_case from backend
      setKtSoll(data.kt_soll || "");
      setKtHaben(data.kt_haben || "");
      setMwstCode(data.mwst_code || "");
      setMwstPct(data.mwst_pct || "");
      setConfidence(data.classification_confidence || data.confidence || 0);
      setClassSource(data.classification_source || data.source || "");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Analyse fehlgeschlagen");
    } finally {
      setExtracting(false);
    }
  }, [file, selectedModel]);

  useEffect(() => {
    if (extractedRef.current) return;
    extractedRef.current = true;
    extract();
  }, [extract]);

  useEffect(() => {
    if (!extracting) { setElapsedSec(0); return; }
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsedSec(Math.round((Date.now() - start) / 1000));
    }, 100);
    return () => clearInterval(interval);
  }, [extracting]);

  const handleAdd = () => {
    const combinedDesc = [vendor, desc].filter(Boolean).join(" - ");
    onAddBooking({
      nr: 0,
      datum: date,
      beleg: "",
      rechnung: invNr,
      beschreibung: combinedDesc,
      kt_soll: ktSoll,
      kt_haben: ktHaben,
      betrag: typeof total === "number" ? total : parseFloat(String(total)) || 0,
      mwstcode: mwstCode,
      artbetrag: "",
      mwstpct: mwstPct,
      mwstchf: mwstPct ? calcMwst(total, mwstPct) : "",
      ks3: "",
    });
    // Learn
    api.post("/api/classify/correct", {
      beschreibung: combinedDesc,
      original_soll: ktSoll,
      original_haben: ktHaben,
      corrected_soll: ktSoll,
      corrected_haben: ktHaben,
      corrected_mwst_code: mwstCode,
      corrected_mwst_pct: mwstPct,
    }).catch(() => {});
    setAdded(true);
    toast.success("Buchung hinzugefügt — gelernt!");
  };

  const isCloud = selectedModel.endsWith(":cloud") || selectedModel.endsWith("-cloud");

  return (
    <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <FileText className="w-4 h-4 text-blue-500" />
          <span className="truncate max-w-[200px]">{file.name}</span>
          <span className="text-[10px] text-gray-400">{(file.size / 1024).toFixed(0)} KB</span>
        </div>
        <button onClick={extract} disabled={extracting}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-white transition-all disabled:opacity-50"
        >
          <RotateCcw className="w-3 h-3" />
          Erneut analysieren
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
        {/* Image */}
        <div className="p-4 flex items-start justify-center bg-gray-50/50 border-r border-gray-100 min-h-[300px]">
          {imageUrl && (
            <img src={imageUrl} alt={file.name} className="max-h-[500px] w-auto rounded-xl shadow-sm object-contain" />
          )}
        </div>

        {/* Results */}
        <div className="p-5 space-y-5 overflow-y-auto max-h-[950px]">
          {extracting && (
            <div className="flex flex-col items-center justify-center py-12 gap-4">
              {/* Animated progress ring */}
              <div className="relative">
                <svg className="w-20 h-20" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="#f3e8ff" strokeWidth="6" />
                  <circle cx="40" cy="40" r="34" fill="none" stroke="#a855f7" strokeWidth="6"
                    strokeLinecap="round"
                    strokeDasharray={`${Math.min(elapsedSec / (isCloud ? 15 : 60), 0.95) * 213.6} 213.6`}
                    className="transition-all duration-300"
                    transform="rotate(-90 40 40)"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-purple-600 tabular-nums">
                  {elapsedSec}s
                </span>
              </div>

              {/* Step indicators */}
              <div className="space-y-2 text-center">
                <p className="text-sm font-medium text-gray-700">
                  {elapsedSec < 1 && "📤 Bild wird hochgeladen..."}
                  {elapsedSec >= 1 && elapsedSec < 3 && "🔄 Bild wird vorbereitet..."}
                  {elapsedSec >= 3 && elapsedSec < 8 && `👁 ${selectedModel} liest Rechnung...`}
                  {elapsedSec >= 8 && elapsedSec < 12 && "🧠 Daten werden extrahiert..."}
                  {elapsedSec >= 12 && elapsedSec < 20 && "🎯 Kontierung wird berechnet..."}
                  {elapsedSec >= 20 && "⏳ Dauert etwas länger als erwartet..."}
                </p>
                <p className="text-xs text-gray-400">
                  {isCloud ? "Cloud-Modell — typisch 5-10s" : "Lokales Modell — typisch 10-30s"}
                </p>
              </div>

              {/* Step progress dots */}
              <div className="flex items-center gap-2">
                {[
                  { label: "Upload", threshold: 0 },
                  { label: "Vision", threshold: 2 },
                  { label: "Extraktion", threshold: 6 },
                  { label: "Kontierung", threshold: 10 },
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all duration-300 ${
                      elapsedSec >= step.threshold
                        ? "bg-purple-100 text-purple-700"
                        : "bg-gray-100 text-gray-400"
                    }`}>
                      {elapsedSec > step.threshold + 3 ? (
                        <CheckCircle className="w-3 h-3 text-emerald-500" />
                      ) : elapsedSec >= step.threshold ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <div className="w-3 h-3 rounded-full border border-gray-300" />
                      )}
                      {step.label}
                    </div>
                    {i < 3 && <div className={`w-4 h-0.5 rounded ${elapsedSec >= step.threshold + 3 ? "bg-purple-300" : "bg-gray-200"}`} />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && !extracting && (
            <div className="flex flex-col items-center py-12 gap-3">
              <XCircle className="w-10 h-10 text-red-400" />
              <p className="text-sm text-red-600 font-medium">Analyse fehlgeschlagen</p>
              <p className="text-xs text-gray-500 text-center max-w-xs">{error}</p>
              <button onClick={extract}
                className="mt-2 flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Erneut versuchen
              </button>
            </div>
          )}

          {result && !extracting && !error && (
            <>
              {/* Pipeline info */}
              {pipelineInfo && (
                <div className="p-3 rounded-xl bg-purple-50 border border-purple-100 text-xs space-y-1">
                  <div className="font-semibold text-purple-700 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5" />
                    Pipeline-Schritte
                  </div>
                  {pipelineInfo.steps.map((step, i) => (
                    <div key={i} className="text-purple-600 pl-5">{step}</div>
                  ))}
                  {pipelineInfo.error && (
                    <div className="text-red-600 pl-5">❌ {pipelineInfo.error}</div>
                  )}
                </div>
              )}

              {/* Extracted fields */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Eye className="w-4 h-4 text-indigo-500" />
                  Erkannte Daten
                </h3>
                <div className="space-y-2.5">
                  <FieldInput label="Lieferant" value={vendor} onChange={setVendor} />
                  <div className="grid grid-cols-2 gap-2.5">
                    <FieldInput label="Datum" value={date} onChange={setDate} />
                    <FieldInput label="Rechnung-Nr." value={invNr} onChange={setInvNr} />
                  </div>
                  <FieldInput label="Beschreibung" value={desc} onChange={setDesc} />

                  {/* Line items */}
                  {result.line_items?.length > 0 && (
                    <>
                      <button onClick={() => setShowLineItems(!showLineItems)}
                        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                      >
                        <List className="w-3.5 h-3.5" />
                        {result.line_items.length} Einzelposten
                        {showLineItems ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                      {showLineItems && result.line_items.map((item, i) => (
                        <div key={i} className="flex justify-between text-xs text-gray-500 pl-5">
                          <span>{item.item}</span>
                          {item.amount > 0 && <span className="font-mono">CHF {item.amount.toFixed(2)}</span>}
                        </div>
                      ))}
                    </>
                  )}

                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">Betrag CHF</label>
                      <input type="number" step="0.01" value={total}
                        onChange={(e) => setTotal(parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">MwSt-% (erkannt)</label>
                      <input type="number" step="0.1" value={vatRate}
                        onChange={(e) => setVatRate(parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Classification */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1.5 flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-purple-500" />
                  Kontierung
                </h3>
                <p className="text-[11px] text-gray-400 mb-3">
                  {sourceIcon(classSource)} {classSource} — Konfidenz: {(confidence * 100).toFixed(0)}%
                </p>
                <div className="space-y-2.5">
                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">KtSoll</label>
                      <input value={ktSoll} onChange={(e) => setKtSoll(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">KtHaben</label>
                      <input value={ktHaben} onChange={(e) => setKtHaben(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2.5">
                    <SelectField label="MwSt-Code" value={mwstCode} onChange={setMwstCode} options={MWST_CODE_OPTIONS} />
                    <SelectField label="MwSt-%" value={mwstPct} onChange={setMwstPct} options={MWST_PCT_OPTIONS} />
                    <div>
                      <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">MwSt CHF</label>
                      <input
                        value={mwstPct ? calcMwst(total, mwstPct).toFixed(2) : ""}
                        disabled
                        className="w-full px-3 py-2 border border-gray-100 rounded-xl text-sm font-mono bg-gray-50 text-gray-500"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Add button */}
              <button onClick={handleAdd} disabled={added}
                className={`w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-semibold rounded-xl transition-all ${
                  added
                    ? "bg-emerald-50 text-emerald-600 border border-emerald-200 cursor-default"
                    : "bg-purple-600 text-white hover:bg-purple-700 shadow-sm shadow-purple-200"
                }`}
              >
                {added ? <><CheckCircle className="w-4 h-4" /> Hinzugefügt ✓ gelernt</> : <><Plus className="w-4 h-4" /> Zur Buchungsliste hinzufügen</>}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Booking Table ────────────────────────────────────────────────────────────
function BookingTable({
  rows, onUpdate, onClear, onRecalcMwst,
}: {
  rows: BuchungRow[]; onUpdate: (rows: BuchungRow[]) => void; onClear: () => void; onRecalcMwst: () => void;
}) {
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [showEmail, setShowEmail] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [sending, setSending] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleFieldChange = (idx: number, field: keyof BuchungRow, value: string | number) => {
    const updated = [...rows];
    (updated[idx] as any)[field] = value;
    onUpdate(updated);
  };

  const handleSave = async () => {
    try {
      const res = await api.post("/api/bookings/", rows.map(row => ({
        datum: row.datum,
        beschreibung: row.beschreibung,
        betrag: Number(row.betrag),
        kt_soll: row.kt_soll,
        kt_haben: row.kt_haben,
        mwst_code: row.mwstcode,
        mwst_pct: row.mwstpct,
        mwst_amount: typeof row.mwstchf === "number" ? row.mwstchf : parseFloat(String(row.mwstchf)) || 0,
        beleg: row.beleg,
        rechnung: row.rechnung,
        source: "rechnung",
      })));
      toast.success(`✅ ${rows.length} Buchung(en) gespeichert!`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Speichern fehlgeschlagen");
    }
  };

  const handleDownload = async (format: "banana" | "excel" | "csv") => {
    setDownloading(format);
    try {
      const res = await api.get(`/api/export/${format}`, {
        params: { source: "rechnung" },
        responseType: "blob",
      });
      const ext = format === "banana" ? "txt" : format === "excel" ? "xlsx" : "csv";
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `buchhaltung_rechnungen.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Download fehlgeschlagen"); }
    finally { setDownloading(null); }
  };

  const handleSendEmail = async () => {
    if (!emailTo || !emailTo.includes("@")) { toast.error("Bitte gültige E-Mail-Adresse eingeben"); return; }
    setSending(true);
    try {
      await api.post("/api/export/email", { to_email: emailTo.trim(), subject: emailSubject.trim() || undefined, source: "rechnung" });
      toast.success("E-Mail gesendet!");
      setShowEmail(false);
    } catch (err: any) { toast.error(err?.response?.data?.detail || "E-Mail fehlgeschlagen"); }
    finally { setSending(false); }
  };

  const headers = ["Nr", "Datum", "Beschreibung", "KtSoll", "KtHaben", "Betrag", "MwSt-Code", "MwSt-%", "MwSt CHF"];

  return (
    <div className="space-y-4">
      {/* Table */}
      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left">
                {headers.map((h) => (
                  <th key={h} className="px-3 py-2.5 text-[11px] font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>
                ))}
                <th className="px-3 py-2.5 w-10" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className={`border-t border-gray-50 ${i % 2 === 1 ? "bg-gray-50/30" : ""} hover:bg-purple-50/30 transition-colors`}>
                  <td className="px-3 py-2 font-mono text-gray-400 text-xs">{row.nr}</td>
                  <td className="px-3 py-2">
                    {editIdx === i ? (
                      <input value={row.datum} onChange={(e) => handleFieldChange(i, "datum", e.target.value)} className="w-24 px-2 py-1 border rounded-lg text-xs" />
                    ) : <span className="text-xs">{row.datum}</span>}
                  </td>
                  <td className="px-3 py-2 max-w-[200px]">
                    {editIdx === i ? (
                      <input value={row.beschreibung} onChange={(e) => handleFieldChange(i, "beschreibung", e.target.value)} className="w-full px-2 py-1 border rounded-lg text-xs" />
                    ) : <span className="text-xs truncate block">{row.beschreibung}</span>}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.kt_soll}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.kt_haben}</td>
                  <td className="px-3 py-2 font-mono text-xs text-right tabular-nums">{Number(row.betrag).toFixed(2)}</td>
                  <td className="px-3 py-2 text-xs">{row.mwstcode}</td>
                  <td className="px-3 py-2 text-xs tabular-nums">{row.mwstpct}</td>
                  <td className="px-3 py-2 font-mono text-xs text-right tabular-nums">
                    {row.mwstchf !== "" && row.mwstchf != null ? Number(row.mwstchf).toFixed(2) : ""}
                  </td>
                  <td className="px-3 py-2">
                    <button onClick={() => setEditIdx(editIdx === i ? null : i)} className="p-1 text-gray-400 hover:text-purple-500 transition-colors">
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition-all shadow-sm shadow-purple-200"
        >
          <Save className="w-4 h-4" /> Speichern
        </button>
        <button onClick={onRecalcMwst}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-gray-200 rounded-xl hover:bg-gray-50 transition-all"
        >
          <Calculator className="w-4 h-4" /> MwSt neu berechnen
        </button>
        <button onClick={() => setShowEmail(!showEmail)}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-gray-200 rounded-xl hover:bg-gray-50 transition-all"
        >
          <Mail className="w-4 h-4" /> E-Mail senden
        </button>
        <div className="flex-1" />
        <button onClick={onClear}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-red-600 border border-red-200 rounded-xl hover:bg-red-50 transition-all"
        >
          <Trash2 className="w-4 h-4" /> Liste leeren
        </button>
      </div>

      {/* Email form */}
      {showEmail && (
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-3 animate-in fade-in slide-in-from-top-1 duration-200">
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <Mail className="w-4 h-4 text-blue-500" /> E-Mail versenden
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldInput label="Empfänger" value={emailTo} onChange={setEmailTo} />
            <FieldInput label="Betreff (optional)" value={emailSubject} onChange={setEmailSubject} />
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleSendEmail} disabled={sending}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-all"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Jetzt senden
            </button>
            <button onClick={() => setShowEmail(false)} className="px-4 py-2.5 text-sm border border-gray-200 rounded-xl hover:bg-gray-50 transition-all">Abbrechen</button>
          </div>
          <p className="text-[11px] text-gray-400">Sendet Banana TXT + CSV als Anhang.</p>
        </div>
      )}

      {/* Downloads */}
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
        <h3 className="font-semibold flex items-center gap-2 text-sm mb-4">
          <Download className="w-4 h-4 text-blue-500" /> Download
        </h3>
        <div className="flex flex-wrap gap-2">
          {([
            { key: "banana" as const, label: "🍌 Banana Import (.txt)", primary: true },
            { key: "excel" as const, label: "📥 Excel (.xlsx)", primary: false },
            { key: "csv" as const, label: "📥 CSV (.csv)", primary: false },
          ]).map(({ key, label, primary }) => (
            <button key={key} onClick={() => handleDownload(key)} disabled={downloading === key}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl transition-all disabled:opacity-50 ${
                primary ? "bg-green-600 text-white hover:bg-green-700 shadow-sm shadow-green-200" : "border border-gray-200 hover:bg-gray-50"
              }`}
            >
              {downloading === key && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Manual Classify Form ─────────────────────────────────────────────────────
function ManualClassifyForm({ onAddBooking }: { onAddBooking: (row: BuchungRow) => void }) {
  const [beschreibung, setBeschreibung] = useState("");
  const [betrag, setBetrag] = useState(0);
  const [datum, setDatum] = useState(new Date().toLocaleDateString("de-CH"));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);

  const handleClassify = async () => {
    if (!beschreibung.trim()) return;
    setLoading(true);
    try {
      const res = await api.post("/api/classify/predict", { beschreibung, betrag });
      setResult(res.data);
    } catch { toast.error("Klassifizierung fehlgeschlagen"); }
    finally { setLoading(false); }
  };

  const handleAdd = () => {
    if (!result) return;
    const mwstChf = result.mwst_pct ? calcMwst(betrag, result.mwst_pct) : 0;
    onAddBooking({
      nr: 0, datum, beleg: "", rechnung: "", beschreibung,
      kt_soll: result.kt_soll, kt_haben: result.kt_haben, betrag,
      mwstcode: result.mwst_code, artbetrag: "", mwstpct: result.mwst_pct,
      mwstchf: mwstChf, ks3: "",
    });
    api.post("/api/classify/correct", {
      beschreibung, original_soll: result.kt_soll, original_haben: result.kt_haben,
      corrected_soll: result.kt_soll, corrected_haben: result.kt_haben,
      corrected_mwst_code: result.mwst_code, corrected_mwst_pct: result.mwst_pct,
    }).catch(() => {});
    toast.success("Buchung hinzugefügt!");
    setBeschreibung(""); setBetrag(0); setResult(null);
  };

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm space-y-4">
      <h2 className="font-semibold flex items-center gap-2">
        <Brain className="w-5 h-5 text-purple-500" />
        Manuelle Klassifizierung (ML-Modell)
      </h2>
      <p className="text-xs text-gray-500">Beschreibung eingeben → ML-Modell klassifiziert automatisch → Buchung hinzufügen</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-2">
          <FieldInput label="Beschreibung" value={beschreibung} onChange={setBeschreibung} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FieldInput label="Datum" value={datum} onChange={setDatum} />
          <div>
            <label className="block text-[11px] font-medium text-gray-400 uppercase mb-1">Betrag</label>
            <input type="number" step="0.01" value={betrag}
              onChange={(e) => setBetrag(parseFloat(e.target.value) || 0)}
              className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-200 transition-all"
            />
          </div>
        </div>
      </div>
      <div className="flex gap-3">
        <button onClick={handleClassify} disabled={loading || !beschreibung.trim()}
          className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white text-sm font-medium rounded-xl hover:bg-purple-700 disabled:opacity-50 transition-all"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Klassifizieren
        </button>
        {result && (
          <button onClick={handleAdd}
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-xl hover:bg-emerald-700 transition-all"
          >
            <Plus className="w-4 h-4" /> Hinzufügen
          </button>
        )}
      </div>
      {result && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 p-4 rounded-xl bg-gray-50 text-sm animate-in fade-in duration-200">
          <div><span className="text-[11px] text-gray-400 uppercase font-semibold block">Quelle</span><div className="font-bold">{sourceIcon(result.source)} {result.source}</div></div>
          <div><span className="text-[11px] text-gray-400 uppercase font-semibold block">KtSoll</span><div className="font-mono font-bold">{result.kt_soll}</div><div className="text-[10px] text-gray-400">{result.kt_soll_name}</div></div>
          <div><span className="text-[11px] text-gray-400 uppercase font-semibold block">KtHaben</span><div className="font-mono font-bold">{result.kt_haben}</div></div>
          <div><span className="text-[11px] text-gray-400 uppercase font-semibold block">MwSt</span><div className="font-mono">{result.mwst_code} {result.mwst_pct}%</div></div>
          <div><span className="text-[11px] text-gray-400 uppercase font-semibold block">Konfidenz</span><div className="font-bold">{(result.confidence * 100).toFixed(0)}%</div></div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function RechnungScannerPage() {
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [buchungen, setBuchungen] = useState<BuchungRow[]>([]);
  const [showTips, setShowTips] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get("/api/scanner/status");
        // console.log("Scanner status:", JSON.stringify(res.data));
        const status: OllamaStatus = res.data;
        setOllamaStatus(status);
        if (status.ok && status.best_vision) {
          setSelectedModel(status.best_vision);
        } else if (status.ok && status.vision_models?.length) {
          setSelectedModel(status.vision_models[0]);
        }
      } catch {
        setOllamaStatus({ ok: false, error: "Ollama nicht erreichbar" });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const visionModels = ollamaStatus?.vision_models ?? [];
  const allModels = (ollamaStatus?.models ?? [])
    .map((m: any) => (typeof m === "string" ? m : m?.name))
    .filter(Boolean) as string[];
  const isVisionModel = visionModels.includes(selectedModel);
  const isCloud = selectedModel.endsWith(":cloud") || selectedModel.endsWith("-cloud");
  const isBuchhaltung = selectedModel === (ollamaStatus?.best_vision || visionModels[0]);
  
  const onDrop = useCallback((files: File[]) => {
    const imageFiles = files.filter((f) => ["image/jpeg", "image/png", "image/webp", "image/bmp"].includes(f.type));
    if (imageFiles.length === 0) { toast.error("Nur Bilder erlaubt (JPG, PNG, WebP, BMP)"); return; }
    setUploadedFiles((prev) => [...prev, ...imageFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp", ".bmp"] },
    multiple: true,
  });

  const addBooking = (row: BuchungRow) => {
    setBuchungen((prev) => {
      const nr = prev.length + 1;
      return [...prev, { ...row, nr }];
    });
  };

  const recalcMwst = () => {
    setBuchungen((prev) =>
      prev.map((r) => ({ ...r, mwstchf: r.mwstpct ? calcMwst(r.betrag, r.mwstpct) : "" }))
    );
    toast.success("MwSt neu berechnet!");
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-80 gap-3">
        <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
        <span className="text-sm text-gray-400">Verbindung zu Ollama...</span>
      </div>
    );
  }

  // Ollama offline — show manual mode
  if (!ollamaStatus?.ok) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto pb-12">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-100"><Camera className="w-6 h-6 text-blue-600" /></div>
            Rechnung Scanner
          </h1>
          <p className="text-gray-500 mt-1.5 text-sm">Vision nicht verfügbar — ML-Klassifizierung aktiv</p>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div>
            <span className="font-medium">Ollama nicht erreichbar.</span>{" "}
            Sie können Buchungen manuell erfassen und vom ML-Modell klassifizieren lassen.
          </div>
        </div>

        {/* Setup instructions */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-gray-700 mb-3">🛠 Setup-Anleitung</h3>
          <ol className="list-decimal list-inside space-y-1.5 text-sm text-gray-600">
            <li>Ollama installieren: <a href="https://ollama.com/download" target="_blank" className="text-purple-600 underline">ollama.com/download</a></li>
            <li>Ollama starten: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">ollama serve</code></li>
            <li>Vision-Modell installieren: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">ollama pull gemma3:12b</code></li>
            <li>
              <button onClick={() => window.location.reload()} className="text-purple-600 underline hover:text-purple-800">
                Seite neu laden
              </button>
            </li>
          </ol>
        </div>

        <ManualClassifyForm onAddBooking={addBooking} />

        {buchungen.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-purple-500" />
              Buchungsliste
              <span className="text-xs font-normal text-gray-400 ml-1">{buchungen.length} Buchungen</span>
            </h2>
            <BookingTable
              rows={buchungen}
              onUpdate={setBuchungen}
              onClear={() => { setBuchungen([]); toast.success("Liste geleert!"); }}
              onRecalcMwst={recalcMwst}
            />
          </div>
        )}
      </div>
    );
  }

  // ── Ollama online — full scanner ──────────────────────────────────────────
  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-blue-100"><Camera className="w-6 h-6 text-blue-600" /></div>
          Rechnung Scanner
        </h1>
        <p className="text-gray-500 mt-1.5 text-sm">Rechnung / Quittung hochladen → AI erkennt automatisch alle Details</p>
      </div>

      {/* Model selector + status */}
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex-1 w-full sm:w-auto">
            <label className="block text-[11px] font-semibold text-gray-400 uppercase mb-1.5">🤖 Modell wählen</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full sm:w-80 px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all appearance-none"
            >
              {/* Buchhaltung Modell — best vision + ML pipeline */}
              {visionModels.length > 0 && (
                <option value={ollamaStatus?.best_vision || visionModels[0]}>
                  🏢 Buchhaltung Modell (Vision + ML Pipeline)
                </option>
              )}
              {/* All other models */}
              {allModels
                .filter((name) => name !== (ollamaStatus?.best_vision || visionModels[0]))
                .map((name, i) => (
                  <option key={`${name}-${i}`} value={name}>
                    {modelDisplayName(name, visionModels)}
                  </option>
                ))}
            </select>
          </div>

          {/* Info badges */}
          <div className="flex items-center gap-3 text-xs">
            {isVisionModel && (
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 font-medium">
                <Eye className="w-3 h-3" /> Vision
              </span>
            )}
            {isCloud && (
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 text-amber-700 font-medium">
                ⚡ Cloud
              </span>
            )}
            <span className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-50 text-purple-700 font-medium">
              <Brain className="w-3 h-3" /> ML aktiv
            </span>
          </div>

        </div>

        {/* Status badge */}
       {isBuchhaltung ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium">
          <CheckCircle className="w-3.5 h-3.5" />
          🏢 Buchhaltung Modell aktiv — {visionModels.length} Vision-Modelle mit Auto-Fallback, ML-Modell klassifiziert automatisch
        </div>
      ) : isVisionModel ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium">
          <Eye className="w-3.5 h-3.5" />
          Vision-Modell aktiv: {selectedModel} + ML-Klassifizierung
        </div>
      ) : (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-xs font-medium">
          <AlertTriangle className="w-3.5 h-3.5" />
          <strong>{selectedModel}</strong> hat keine Vision-Fähigkeit
        </div>
      )}
      </div>

      {/* Manual classify — always available */}
      <ManualClassifyForm onAddBooking={addBooking} />

      {/* Upload zone */}
      <div
        {...getRootProps()}
        className={`rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
          isDragActive ? "border-blue-400 bg-blue-50/80" : "border-gray-200 hover:border-purple-300 hover:bg-purple-50/30"
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          <div className="p-4 rounded-2xl bg-gray-100"><Camera className="w-8 h-8 text-gray-400" /></div>
          <div>
            <p className="text-gray-600 font-medium">Rechnung / Quittung hierher ziehen oder klicken</p>
            <p className="text-xs text-gray-400 mt-1">JPG, PNG, WebP, BMP — mehrere Dateien möglich</p>
          </div>
        </div>
      </div>

      {/* Scanned invoices */}
      {uploadedFiles.map((file, i) => (
        <InvoiceCard
          key={`${file.name}-${file.size}-${i}`}
          file={file}
          selectedModel={selectedModel}
          onAddBooking={addBooking}
        />
      ))}

      {/* Booking list */}
      {buchungen.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5 text-purple-500" />
            Buchungsliste
            <span className="text-xs font-normal text-gray-400 ml-1">{buchungen.length} Buchungen</span>
          </h2>
          <BookingTable
            rows={buchungen}
            onUpdate={setBuchungen}
            onClear={() => { setBuchungen([]); toast.success("Liste geleert!"); }}
            onRecalcMwst={recalcMwst}
          />
        </div>
      )}

      {/* Empty state */}
      {buchungen.length === 0 && uploadedFiles.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Camera className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Noch keine Rechnungen. Laden Sie eine Rechnung hoch, um zu beginnen.</p>
        </div>
      )}
    </div>
  );
}
