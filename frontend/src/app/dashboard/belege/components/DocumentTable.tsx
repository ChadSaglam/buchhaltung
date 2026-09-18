import { CheckCircle2, CreditCard, ExternalLink, Mail, MailCheck, QrCode, RotateCcw } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import api from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import toast from "react-hot-toast";
import { cn } from "@/lib/utils";
import { STATUS_LABEL, STATUS_TONE, formatCHF, formatDate, isOverdue, sourceLabel } from "../helpers";
import { gesendetLabel } from "../versand";
import type { DocumentOut, DocumentStatus } from "../types";

interface Props {
  items: DocumentOut[];
  onStatus: (doc: DocumentOut, status: DocumentStatus) => void;
  /** B-89: "war schon bezahlt" — keeps the row out of "Was schulden wir". */
  onPaidAtSource?: (doc: DocumentOut, paid: boolean) => void;
  /** Open the mail preview for one of our own invoices (B-79). */
  onSenden?: (doc: DocumentOut) => void;
  sendenLoadingId?: number | null;
}

/** Only an invoice we wrote ourselves can be mailed to a customer. */
function istEigeneRechnung(doc: DocumentOut): boolean {
  return doc.direction === "ausgang";
}

const COLS = ["Lieferant", "Nr.", "Datum", "Fällig", "Betrag", "Konto", "Quelle", "Status", ""];

/** The file endpoint needs the bearer token, so a plain <a href> would 401 — fetch as blob and open. */
async function openFile(doc: DocumentOut) {
  try {
    const res = await api.get(`/api/documents/${doc.id}/file`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (e) {
    toast.error(errorMessage(e));
  }
}

export function DocumentTable({ items, onStatus, onPaidAtSource, onSenden, sendenLoadingId }: Props) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[860px]" aria-label="Rechnungen">
          <thead>
            <tr className="bg-muted border-b border-border text-left">
              {COLS.map((h, i) => (
                <th key={i} scope="col" className="px-3 py-3 font-medium text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((d) => {
              const overdue = isOverdue(d);
              const status = d.status as DocumentStatus;
              return (
                <tr key={d.id} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                  <td className="px-3 py-2 max-w-[260px]">
                    <p className="truncate text-foreground font-medium">{d.vendor || <span className="text-muted-foreground italic">unbekannt</span>}</p>
                    <p className="truncate text-xs text-muted-foreground">{d.error || d.qr_message || d.filename}</p>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{d.invoice_no || "–"}</td>
                  <td className="px-3 py-2 tabular-nums text-muted-foreground">{formatDate(d.invoice_date)}</td>
                  <td className={cn("px-3 py-2 tabular-nums", overdue ? "text-destructive font-medium" : "text-muted-foreground")}>
                    {formatDate(d.due_date)}
                  </td>
                  <td className="px-3 py-2 font-mono text-right tabular-nums text-foreground whitespace-nowrap">{formatCHF(d.amount, d.currency)}</td>
                  <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                    {d.kt_soll ? (
                      <span title={`Konfidenz ${Math.round(d.classification_confidence * 100)}%`}>
                        <span className="text-brand-600 dark:text-brand-300">{d.kt_soll}</span> / <span className="text-success">{d.kt_haben}</span>
                        {d.mwst_code && <span className="ml-1 text-muted-foreground">{d.mwst_code}</span>}
                      </span>
                    ) : "–"}
                  </td>
                  <td className="px-3 py-2">
                    <span title={sourceLabel(d.extraction_source)} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      {d.extraction_source === "qr" && <QrCode className="h-3.5 w-3.5 text-success" aria-hidden="true" />}
                      {sourceLabel(d.extraction_source)}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge tone={d.paid_at_source && status === "offen" ? "neutral" : STATUS_TONE[status] ?? "neutral"} dot>
                        {d.paid_at_source && status === "offen" ? "Bezahlt an der Kasse" : overdue ? "Überfällig" : STATUS_LABEL[status] ?? d.status}
                      </Badge>
                      {d.sent_at && (
                        <span title={gesendetLabel(d.sent_at)} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <MailCheck className="h-3.5 w-3.5 text-success" aria-hidden="true" />
                          <span className="sr-only">{gesendetLabel(d.sent_at)}</span>
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1">
                      {status === "offen" && onPaidAtSource && (
                        <button
                          type="button"
                          onClick={() => onPaidAtSource(d, !d.paid_at_source)}
                          aria-pressed={Boolean(d.paid_at_source)}
                          title={
                            d.paid_at_source
                              ? "Bereits an der Kasse bezahlt (Karte/Bar) — steht nicht unter «Was schulden wir». Klicken, um das zurückzunehmen."
                              : "War beim Kauf schon bezahlt (Karte/Bar)? Dann ist es keine offene Schuld."
                          }
                          aria-label={`${d.vendor || d.filename}: bereits an der Kasse bezahlt ${d.paid_at_source ? "aufheben" : "markieren"}`}
                          className={cn(
                            "rounded-md p-1.5 transition-colors",
                            d.paid_at_source
                              ? "text-success hover:bg-accent"
                              : "text-muted-foreground hover:bg-accent hover:text-foreground",
                          )}
                        >
                          <CreditCard className="h-4 w-4" aria-hidden="true" />
                        </button>
                      )}
                      {status === "offen" && (
                        <Button size="xs" variant="success" onClick={() => onStatus(d, "bezahlt")} icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />} aria-label={`${d.vendor || d.filename} als bezahlt markieren`}>
                          Bezahlt
                        </Button>
                      )}
                      {status === "bezahlt" && (
                        <Button size="xs" variant="ghost" onClick={() => onStatus(d, "offen")} icon={<RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />} aria-label={`${d.vendor || d.filename} wieder öffnen`}>
                          Offen
                        </Button>
                      )}
                      {onSenden && istEigeneRechnung(d) && (
                        <Button
                          size="xs"
                          variant="ghost"
                          loading={sendenLoadingId === d.id}
                          onClick={() => onSenden(d)}
                          icon={<Mail className="h-3.5 w-3.5" aria-hidden="true" />}
                          aria-label={`Rechnung ${d.invoice_no || d.filename} per E-Mail senden`}
                        >
                          {d.sent_at ? "Erneut" : "Senden"}
                        </Button>
                      )}
                      <button
                        type="button"
                        onClick={() => openFile(d)}
                        aria-label={`Datei ${d.filename} öffnen`}
                        className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                      >
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
