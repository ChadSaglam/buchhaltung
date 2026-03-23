"use client";

import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Save, User, Building2, Bell, Palette, Shield, Loader2, Check } from "lucide-react";
import { api, getMe } from "@/lib/api";
import { cn } from "@/lib/utils";

interface UserInfo {
  id: number;
  email: string;
  display_name: string;
  role: string;
  tenant_id: number;
  tenant_name: string;
}

type TabId = "profile" | "company" | "notifications" | "appearance" | "security";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ElementType;
}

const TABS: Tab[] = [
  { id: "profile", label: "Profil", icon: User },
  { id: "company", label: "Unternehmen", icon: Building2 },
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
      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-shadow"
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
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");

  useEffect(() => {
    getMe().then((u) => {
      setUser(u);
      setDisplayName(u.display_name);
      setCompanyName(u.tenant_name);
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await new Promise((r) => setTimeout(r, 600));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Einstellungen</h1>
          <p className="mt-1 text-sm text-muted-foreground">Konto- und Anwendungseinstellungen verwalten</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-all",
            saved
              ? "bg-emerald-600 hover:bg-emerald-700"
              : "bg-brand-600 hover:bg-brand-700 shadow-md shadow-brand-600/25"
          )}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" />
           : saved ? <Check className="h-4 w-4" />
           : <Save className="h-4 w-4" />}
          {saved ? "Gespeichert" : "Speichern"}
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Tab navigation */}
        <nav className="flex md:flex-col gap-1 md:w-56 shrink-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all text-left",
                activeTab === tab.id
                  ? "bg-brand-50 text-brand-700"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab content */}
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
                <span className="inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 capitalize">
                  {user?.role ?? "–"}
                </span>
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
              <p className="text-sm text-muted-foreground mb-6">Theme und Anzeige anpassen</p>
              <SettingsField label="Theme" description="Hell, Dunkel oder System">
                <div className="flex gap-2">
                  {(["light", "dark", "system"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setTheme(t)}
                      className={cn(
                        "rounded-lg border px-4 py-2 text-sm font-medium transition-all capitalize",
                        theme === t
                          ? "border-brand-600 bg-brand-50 text-brand-700"
                          : "border-border text-muted-foreground hover:border-brand-200"
                      )}
                    >
                      {t === "light" ? "Hell" : t === "dark" ? "Dunkel" : "System"}
                    </button>
                  ))}
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
