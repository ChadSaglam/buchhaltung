"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { Mail, Lock, User, Building2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/input";
import { LogoMark } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { register as apiRegister, getMe } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await apiRegister(email, password, tenantName || "Meine Firma", displayName);
      localStorage.setItem("token", access_token);
      const user = await getMe();
      setAuth(access_token, user);
      router.push("/dashboard");
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Registrierung fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-[0.4]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-brand-500/20 blur-[120px]" />

      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-md"
      >
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="h-12 w-12">
            <LogoMark />
          </div>
          <h1 className="mt-4 text-xl font-bold tracking-tight text-foreground">Konto erstellen</h1>
          <p className="mt-1 text-sm text-muted-foreground">Starten Sie mit Ihrer Buchhaltung</p>
        </div>

        <div className="card-elevated p-6 shadow-lg">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Firmenname</label>
              <Input placeholder="Meine Firma GmbH" icon={<Building2 />} value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Ihr Name</label>
              <Input placeholder="Max Muster" icon={<User />} value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">E-Mail</label>
              <Input type="email" placeholder="name@firma.ch" icon={<Mail />} value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Passwort</label>
              <Input type="password" placeholder="Mindestens 8 Zeichen" icon={<Lock />} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
            </div>
            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </motion.p>
            )}
            <Button type="submit" size="lg" className="w-full" loading={loading} iconRight={<ArrowRight className="h-4 w-4" />}>
              Registrieren
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Bereits registriert?{" "}
          <a href="/login" className="font-semibold text-brand-600 hover:underline dark:text-brand-300">
            Anmelden
          </a>
        </p>
      </motion.div>
    </div>
  );
}
