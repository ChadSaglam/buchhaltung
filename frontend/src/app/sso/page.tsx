"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShieldAlert } from "lucide-react";
import { LogoMark } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ssoLogin, getMe } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { toAppError } from "@/lib/errors";
import { t } from "@/lib/i18n";

/**
 * SSO landing (chadev-platform/contracts/sso.md). billing sends the browser
 * to `/sso#token=…`; the token lives only in the fragment (never in a server
 * log), is read once on mount, cleared from the URL, exchanged for a regular
 * session and the user lands on the dashboard — exactly what /login does.
 */

const KNOWN_CODES = new Set(["sso_invalid", "sso_expired", "sso_replayed", "email_taken_locally", "http_404"]);

function readTokenFromHash(): string | null {
  const hash = window.location.hash.replace(/^#/, "");
  const token = new URLSearchParams(hash).get("token");
  return token && token.trim() ? token.trim() : null;
}

export default function SsoPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [error, setError] = useState<string | null>(null);
  // The token is single-use: the exchange must run exactly once, even though
  // React's dev StrictMode mounts, unmounts and re-mounts (re-running effects).
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = readTokenFromHash();
    // Drop the fragment immediately so a reload or a copied URL cannot replay it.
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    if (!token) {
      setError(t("sso.error_missing"));
      return;
    }
    (async () => {
      try {
        const { access_token } = await ssoLogin(token);
        localStorage.setItem("token", access_token);
        const user = await getMe();
        setAuth(access_token, user);
        router.replace("/dashboard");
      } catch (err) {
        const appError = toAppError(err);
        setError(KNOWN_CODES.has(appError.code) ? t(`sso.error_${appError.code}`) : appError.message);
      }
    })();
  }, [router, setAuth]);

  return (
    <main id="main" className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-[0.4]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-brand-500/20 blur-[120px]" />

      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="h-12 w-12">
            <LogoMark />
          </div>
          <h1 className="mt-4 text-xl font-bold tracking-tight text-foreground">{t("sso.title")}</h1>
        </div>

        <div className="card-elevated p-6 shadow-lg">
          {error ? (
            <div role="alert" className="flex flex-col items-center gap-3 text-center">
              <ShieldAlert className="h-8 w-8 text-destructive" aria-hidden="true" />
              <p className="text-sm font-semibold text-foreground">{t("sso.error_title")}</p>
              <p className="text-sm text-muted-foreground">{error}</p>
              <a
                href="/login"
                className="mt-2 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {t("sso.to_login")}
              </a>
            </div>
          ) : (
            <div role="status" aria-live="polite" className="flex items-center justify-center gap-3 py-2">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">{t("sso.loading")}</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
