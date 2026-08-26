import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <Compass className="h-7 w-7" aria-hidden="true" />
        </div>
        <h1 className="mt-5 text-lg font-semibold text-foreground">Seite nicht gefunden</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Diese Adresse gibt es nicht. Vielleicht wurde die Seite verschoben.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:brightness-110"
        >
          Zum Dashboard
        </Link>
      </div>
    </main>
  );
}
