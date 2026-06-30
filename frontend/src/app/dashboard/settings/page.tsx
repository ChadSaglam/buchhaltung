"use client";

import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Save, User, Building2, Bell, Palette, Shield, SlidersHorizontal, Check, Settings, Sun, Moon, Monitor } from "lucide-react";
import { getMe, getScannerConfig, updateScannerConfig } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useThemeStore, ACCENTS, type Theme, type Accent } from "@/lib/theme-store";

interface UserInfo {
  id: number;
  email: string;
  display_name: string;
  role: string;
  tenant_id: number;
  tenant_name: string;
}

type TabId = "profile" | "company" | "notifications" | "appearance" | "security" | "review";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ElementType;
}

const THEME_OPTIONS: { id: Theme; label: string; icon: React.ElementType }[] = [
  { id: "light", label: "Hell", icon: Sun },
  { id: "dark", label: "Dunkel", icon: Moon },
  { id: "system", label: "System", icon: Monitor },
];

const TABS: Tab[] = [
  { id: "profile", label: "Profil", icon: User },
  { id: "company", label: "Unternehmen", icon: Building2 },
  { id: "review", label: "Überprüfung", icon: SlidersHorizontal },
  { id: "notifications", label: "Benachrichtigungen", icon: Bell },
  { id: "appearance", label: "Darstellung", icon: Palette },
  { id: "security", label: "Sicherheit", icon: Shield },
];

function SettingsField({ label, description, children }: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-8 py-5 border-b border-border last:border-0">
      <div className="sm:w-1/3">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="sm:w-2/3">{children}</div>
    </div>
  );
}

function SettingsInput({ value, onChange, type = "text", placeholder }: {
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-shadow"
    />
  );
}

function SettingsToggle({ checked, onChange, label }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-sm text-foreground">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
          checked ? "bg-brand-600" : "bg-muted"
        )}
      >
        <span className={cn(
          "inline-block h-4 w-4 rounded-full bg-white transition-transform",
          checked ? "translate-x-6" : "translate-x-1"
        )} />
      </button>
    </label>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [user, setUser] = useState<UserInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [emailNotifs, setEmailNotifs] = useState(true);
  const [exportNotifs, setExportNotifs] = useState(true);
  const { theme, accent, setTheme, setAccent } = useThemeStore();

  const [threshold, setThreshold] = useState(0.8);
  const [configLoaded, setConfigLoaded] = useState(false);

  useEffect(() => {
    getMe().then((u) => {
      setUser(u);
      setDisplayName(u.display_name);
      setCompanyName(u.tenant_name);
    }).catch(() => {});

    getScannerConfig().then((c) => {
      if (typeof c.review_confidence_threshold === "number") {
        setThreshold(c.review_confidence_threshold);
      }
      setConfigLoaded(true);
    }).catch(() => setConfigLoaded(true));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (activeTab === "review" && configLoaded) {
        await updateScannerConfig({ review_confidence_threshold: threshold });
      } else {
        await new Promise((r) => setTimeout(r, 600));
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Settings}
        title="Einstellungen"
        subtitle="Konto- und Anwendungseinstellungen verwalten"
        action={
          <Button
            variant={saved ? "success" : "primary"}
            onClick={handleSave}
            disabled={saving}
            loading={saving}
            icon={saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          >
            {saved ? "Gespeichert" : "Speichern"}
          </Button>
        }
      />

      <div className="flex flex-col md:flex-row gap-6">
        <nav className="flex md:flex-col gap-1 md:w-56 shrink-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all text-left",
                activeTab === tab.id
                  ? "bg-brand-500/12 text-brand-600 dark:text-brand-300"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>

        <motion.div
          key={activeTab}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
          className="flex-1 rounded-xl border border-border bg-card p-6"
        >
          {activeTab === "profile" && (
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">Profil</h2>
              <p className="text-sm text-muted-foreground mb-6">Persönliche Informationen verwalten</p>
              <SettingsField label="Anzeigename" description="Wird in der App angezeigt">
                <SettingsInput value={displayName} onChange={setDisplayName} />
              </SettingsField>
              <SettingsField label="E-Mail" description="Anmelde-E-Mail (nicht änderbar)">
                <p className="text-sm text-muted-foreground py-2">{user?.email ?? "–"}</p>
              </SettingsField>
              <SettingsField label="Rolle">
                <Badge tone="brand" className="capitalize">{user?.role ?? "–"}</Badge>
              </SettingsField>
            </div>
          )}

          {activeTab === "company" && (
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">Unternehmen</h2>
              <p className="text-sm text-muted-foreground mb-6">Firmendaten verwalten</p>
              <SettingsField label="Firmenname">
                <SettingsInput value={companyName} onChange={setCompanyName} />
              </SettingsField>
              <SettingsField label="Mandanten-ID">
                <p className="font-mono text-sm text-muted-foreground py-2">{user?.tenant_id ?? "–"}</p>
              </SettingsField>
            </div>
          )}

          {activeTab === "review" && (
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">Überprüfung</h2>
              <p className="text-sm text-muted-foreground mb-6">Schwelle für die Überprüfungs-Warteschlange festlegen</p>
              <SettingsField
                label="Konfidenz-Schwelle"
                description="Vorhersagen unter diesem Wert landen in der Überprüfungs-Warteschlange"
              >
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={threshold}
                    onChange={(e) => setThreshold(parseFloat(e.target.value))}
                    className="flex-1 accent-brand-600"
                    aria-label="Konfidenz-Schwelle"
                  />
                  <span className="w-16 text-right font-mono text-sm text-foreground tabular-nums">
                    {Math.round(threshold * 100)}%
                  </span>
                </div>
              </SettingsField>
            </div>
          )}

          {activeTab === "notifications" && (
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">Benachrichtigungen</h2>
              <p className="text-sm text-muted-foreground mb-6">E-Mail- und App-Benachrichtigungen</p>
              <SettingsField label="E-Mail-Benachrichtigungen">
                <div className="space-y-4">
                  <SettingsToggle checked={emailNotifs} onChange={setEmailNotifs} label="Tägliche Zusammenfassung" />
                  <SettingsToggle checked={exportNotifs} onChange={setExportNotifs} label="Export-Bestätigung per E-Mail" />
                </div>
              </SettingsField>
            </div>
          )}

          {activeTab === "appearance" && (
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">Darstellung</h2>
              <p className="text-sm text-muted-foreground mb-6">Theme und Akzentfarbe anpassen — Änderungen werden sofort übernommen</p>
              <SettingsField label="Theme" description="Hell, Dunkel oder automatisch nach System">
                <div className="grid grid-cols-3 gap-3">
                  {THEME_OPTIONS.map((opt) => {
                    const active = theme === opt.id;
                    return (
                      <button
                        key={opt.id}
                        onClick={() => setTheme(opt.id)}
                        aria-pressed={active}
                        className={cn(
                          "group relative flex flex-col items-center gap-2 rounded-xl border-2 p-3 transition-all",
                          active
                            ? "border-primary bg-brand-500/8"
                            : "border-border hover:border-border-strong"
                        )}
                      >
                        <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg", active ? "bg-brand-500/15 text-brand-600 dark:text-brand-300" : "bg-muted text-muted-foreground")}>
                          <opt.icon className="h-[18px] w-[18px]" />
                        </span>
                        <span className={cn("text-xs font-medium", active ? "text-foreground" : "text-muted-foreground")}>{opt.label}</span>
                        {active && (
                          <span className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
                            <Check className="h-2.5 w-2.5" />
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </SettingsField>
              <SettingsField label="Akzentfarbe" description="Bestimmt Buttons, Links und Hervorhebungen">
                <div className="flex flex-wrap gap-3">
                  {(Object.keys(ACCENTS) as Accent[]).map((key) => {
                    const a = ACCENTS[key];
                    const active = accent === key;
                    return (
                      <button
                        key={key}
                        onClick={() => setAccent(key)}
                        aria-label={a.label}
                        title={a.label}
                        className={cn(
                          "relative flex h-10 w-10 items-center justify-center rounded-full transition-transform hover:scale-105",
                          active && "ring-2 ring-offset-2 ring-offset-card"
                        )}
                        style={{ backgroundColor: a.swatch, ...(active ? { boxShadow: `0 0 0 2px ${a.swatch}` } : {}) }}
                      >
                        {active && <Check className="h-4 w-4 text-white" />}
                      </button>
                    );
                  })}
                </div>
              </SettingsField>
            </div>
          )}

          {activeTab === "security" && (
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">Sicherheit</h2>
              <p className="text-sm text-muted-foreground mb-6">Passwort und Sicherheitsoptionen</p>
              <SettingsField label="Passwort ändern">
                <div className="space-y-3">
                  <SettingsInput value="" onChange={() => {}} type="password" placeholder="Aktuelles Passwort" />
                  <SettingsInput value="" onChange={() => {}} type="password" placeholder="Neues Passwort" />
                  <SettingsInput value="" onChange={() => {}} type="password" placeholder="Passwort bestätigen" />
                </div>
              </SettingsField>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
