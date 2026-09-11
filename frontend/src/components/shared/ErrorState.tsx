"use client";
import { AlertCircle, RefreshCw, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { toAppError } from "@/lib/errors";
import { t } from "@/lib/i18n";

interface Props {
  /** Anything a fetch can reject with — normalised through `toAppError`. */
  error: unknown;
  /** Re-runs the request (SWR `mutate`, a `load()` from a hook, …). */
  onRetry?: () => void;
  title?: string;
  icon?: LucideIcon;
  /** `inline` = compact row inside a card; `page` = centred block. */
  variant?: "page" | "inline";
  className?: string;
}

/**
 * The one way a failed request is shown. Renders the envelope's
 * `error.message` (already German and actionable, see `lib/errors.ts`), the
 * request id for bug reports, and a retry button when the caller can retry.
 */
export function ErrorState({ error, onRetry, title, icon: Icon = AlertCircle, variant = "page", className = "" }: Props) {
  const e = toAppError(error);
  const heading = title ?? t("state.error_title");

  if (variant === "inline") {
    return (
      <div
        role="alert"
        className={`flex flex-wrap items-center gap-3 rounded-lg border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm ${className}`}
      >
        <Icon className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
        <span className="min-w-0 flex-1 text-foreground">
          <span className="font-medium">{heading}: </span>
          {e.message}
          {e.requestId && <span className="ml-1 text-xs text-muted-foreground">({t("state.request_ref")}: {e.requestId})</span>}
        </span>
        {onRetry && (
          <Button variant="outline" size="xs" onClick={onRetry} icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}>
            {t("state.retry")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <div role="alert" className={`flex flex-col items-center justify-center px-6 py-16 text-center ${className}`}>
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <Icon className="h-7 w-7" aria-hidden="true" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-foreground">{heading}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{e.message}</p>
      {e.requestId && (
        <p className="mt-1 font-mono text-xs text-muted-foreground">
          {t("state.request_ref")}: {e.requestId}
        </p>
      )}
      {onRetry && (
        <Button variant="outline" className="mt-6" onClick={onRetry} icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}>
          {t("state.retry")}
        </Button>
      )}
    </div>
  );
}
