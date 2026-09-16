import { Download, FileText, Package } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/format";
import { batchSubtitle, formatPeriod } from "../helpers";
import type { ExportBatchOut } from "../types";

interface Props {
  batches: ExportBatchOut[];
  onFile: (batch: ExportBatchOut) => void;
  onCover: (batch: ExportBatchOut) => void;
  /** B-17: cover sheet, Banana file, receipts and audit trail in one zip. */
  onPack: (batch: ExportBatchOut) => void;
  /** Id of the batch whose pack is building, or null. */
  packing: number | null;
}

export function BatchList({ batches, onFile, onCover, onPack, packing }: Props) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Frühere Exporte">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="px-4 py-2 font-medium">Export</th>
              <th scope="col" className="px-4 py-2 font-medium">Zeitraum</th>
              <th scope="col" className="px-4 py-2 font-medium">Inhalt</th>
              <th scope="col" className="px-4 py-2 font-medium">Erstellt</th>
              <th scope="col" className="px-4 py-2 font-medium text-right">Dateien</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {batches.map((batch) => (
              <tr key={batch.id} className="hover:bg-accent/40">
                <td className="px-4 py-2.5 font-medium text-foreground">#{batch.id}</td>
                <td className="px-4 py-2.5 text-muted-foreground">
                  {formatPeriod(batch.period_from, batch.period_to)}
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">
                  {batchSubtitle(batch.booking_count, batch.total_betrag)}
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">{formatDate(batch.created_at)}</td>
                <td className="px-4 py-2.5">
                  <div className="flex justify-end gap-2">
                    <Button size="xs" variant="secondary" icon={<Download className="h-3.5 w-3.5" />} onClick={() => onFile(batch)}>
                      Banana
                    </Button>
                    <Button size="xs" variant="ghost" icon={<FileText className="h-3.5 w-3.5" />} onClick={() => onCover(batch)}>
                      Deckblatt
                    </Button>
                    <Button
                      size="xs"
                      variant="secondary"
                      icon={<Package className="h-3.5 w-3.5" />}
                      onClick={() => onPack(batch)}
                      loading={packing === batch.id}
                      disabled={packing !== null}
                      title="Deckblatt, Banana-Datei, Belege und Protokoll in einem ZIP"
                    >
                      Für die Treuhand
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
