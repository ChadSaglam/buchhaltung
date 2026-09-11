import { Badge } from "@/components/ui/Badge";
import { SettingsField, SettingsInput } from "./SettingsPrimitives";
import type { UserInfo } from "../types";

export function ProfileTab({ user, displayName, setDisplayName }: {
  user: UserInfo | null;
  displayName: string;
  setDisplayName: (v: string) => void;
}) {
  return (
    <div>
      <h2 className="text-base font-semibold text-foreground mb-1">Profil</h2>
      <p className="text-sm text-muted-foreground mb-6">Persönliche Informationen verwalten</p>
      <SettingsField label="Anzeigename" description="Wird in der App angezeigt">
        <SettingsInput value={displayName} onChange={setDisplayName} label="Anzeigename" />
      </SettingsField>
      <SettingsField label="E-Mail" description="Anmelde-E-Mail (nicht änderbar)">
        <p className="text-sm text-muted-foreground py-2">{user?.email ?? "–"}</p>
      </SettingsField>
      <SettingsField label="Rolle">
        <Badge tone="brand" className="capitalize">{user?.role ?? "–"}</Badge>
      </SettingsField>
    </div>
  );
}

export function CompanyTab({ user, companyName, setCompanyName }: {
  user: UserInfo | null;
  companyName: string;
  setCompanyName: (v: string) => void;
}) {
  return (
    <div>
      <h2 className="text-base font-semibold text-foreground mb-1">Unternehmen</h2>
      <p className="text-sm text-muted-foreground mb-6">Firmendaten verwalten</p>
      <SettingsField label="Firmenname">
        <SettingsInput value={companyName} onChange={setCompanyName} label="Firmenname" />
      </SettingsField>
      <SettingsField label="Mandanten-ID">
        <p className="font-mono text-sm text-muted-foreground py-2">{user?.tenant_id ?? "–"}</p>
      </SettingsField>
    </div>
  );
}

export function SecurityTab() {
  return (
    <div>
      <h2 className="text-base font-semibold text-foreground mb-1">Sicherheit</h2>
      <p className="text-sm text-muted-foreground mb-6">Passwort und Sicherheitsoptionen</p>
      <SettingsField label="Passwort ändern">
        <div className="space-y-3">
          <SettingsInput value="" onChange={() => {}} type="password" placeholder="Aktuelles Passwort" label="Aktuelles Passwort" />
          <SettingsInput value="" onChange={() => {}} type="password" placeholder="Neues Passwort" label="Neues Passwort" />
          <SettingsInput value="" onChange={() => {}} type="password" placeholder="Passwort bestätigen" label="Passwort bestätigen" />
        </div>
      </SettingsField>
    </div>
  );
}
