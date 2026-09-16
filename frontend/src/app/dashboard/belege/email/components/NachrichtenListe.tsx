import { Check, Mail } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { STATUS_LABEL, STATUS_TONE, type EmailMessageOut } from "../types";
import { absenderBekannt } from "../helpers";

function tag(status: string) {
  return { label: STATUS_LABEL[status] ?? status, tone: STATUS_TONE[status] ?? "neutral" } as const;
}

export function NachrichtenListe({ nachrichten, absender, onErlauben }: {
  nachrichten: EmailMessageOut[];
  absender: string[];
  onErlauben: (adresse: string) => void;
}) {
  if (nachrichten.length === 0) {
    return (
      <EmptyState
        icon={Mail}
        title="Noch keine Nachricht"
        description="Leite eine Rechnung an die Adresse oben weiter — sie erscheint hier, sobald sie angekommen ist."
      />
    );
  }

  return (
    <ul className="divide-y divide-border">
      {nachrichten.map((m) => {
        const { label, tone } = tag(m.status);
        const bekannt = absenderBekannt(m.from_addr, absender);
        return (
          <li key={m.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">{m.subject || "(kein Betreff)"}</span>
                <Badge tone={tone}>{label}</Badge>
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {m.from_addr || "(unbekannt)"}
                {m.document_count > 0 && ` · ${m.document_count} Beleg${m.document_count === 1 ? "" : "e"}`}
                {m.attachment_count > 0 && m.document_count === 0 && ` · ${m.attachment_count} Anhang/Anhänge`}
              </p>
              {m.reason && <p className="mt-1 text-xs text-muted-foreground">{m.reason}</p>}
            </div>
            {m.status === "abgelehnt" && m.from_addr && !bekannt && (
              <Button
                variant="secondary"
                size="sm"
                icon={<Check className="h-4 w-4" />}
                onClick={() => onErlauben(m.from_addr)}
              >
                Absender erlauben
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
