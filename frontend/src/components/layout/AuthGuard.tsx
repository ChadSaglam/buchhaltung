"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogoMark } from "@/components/ui/Logo";

/**
 * Client-side route guard for the dashboard. Redirects unauthenticated
 * visitors to /login before rendering any protected content. Backend
 * authorization still enforces data access; this fixes the UX + e2e
 * expectation that /dashboard redirects when no token is present.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      router.replace("/login");
      return;
    }
    setChecked(true);
  }, [router]);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-11 w-11 animate-pulse-ring rounded-xl">
            <LogoMark />
          </div>
          <p className="text-sm text-muted-foreground">Wird geladen…</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
