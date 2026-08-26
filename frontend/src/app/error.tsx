"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/Button";

/**
 * Route-level error boundary. Next.js renders this instead of a blank screen
 * whenever a page or its data throws.
 */
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[route error]", error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
          <AlertTriangle className="h-7 w-7" aria-hidden="true" />
        </div>
        <h1 className="mt-5 text-lg font-semibold text-foreground">Da ist etwas schiefgelaufen</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Diese Seite konnte nicht geladen werden. Deine Daten sind sicher — versuche es nochmals.
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-xs text-muted-foreground">Ref: {error.digest}</p>
        )}
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button onClick={reset} icon={<RotateCw className="h-4 w-4" />}>
            Nochmals versuchen
          </Button>
          <Link href="/dashboard">
            <Button variant="secondary" icon={<Home className="h-4 w-4" />}>
              Zum Dashboard
            </Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
