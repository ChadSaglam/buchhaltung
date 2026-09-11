"use client";

import { motion } from "motion/react";
import { Save, Check, Settings } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { useSettings } from "./hooks/useSettings";
import { SettingsTabs } from "./components/SettingsTabs";
import { ProfileTab, CompanyTab, SecurityTab } from "./components/AccountTabs";
import { ReviewTab, NotificationsTab } from "./components/PreferenceTabs";
import { AppearanceTab } from "./components/AppearanceTab";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";

export default function SettingsPage() {
  const s = useSettings();

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Settings}
        title="Einstellungen"
        subtitle="Konto- und Anwendungseinstellungen verwalten"
        action={
          <Button
            variant={s.saved ? "success" : "primary"}
            onClick={s.handleSave}
            disabled={s.saving}
            loading={s.saving}
            icon={s.saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          >
            {s.saved ? "Gespeichert" : "Speichern"}
          </Button>
        }
      />

      <div className="flex flex-col md:flex-row gap-6">
        <SettingsTabs activeTab={s.activeTab} onSelect={s.setActiveTab} />

        <motion.div
          key={s.activeTab}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
          className="flex-1 rounded-xl border border-border bg-card p-6"
        >
          {s.loading ? (
            <PageSkeleton rows={3} />
          ) : s.error ? (
            <ErrorState error={s.error} onRetry={s.load} />
          ) : (
            <>
              {s.activeTab === "profile" && (
                <ProfileTab user={s.user} displayName={s.displayName} setDisplayName={s.setDisplayName} />
              )}
              {s.activeTab === "company" && (
                <CompanyTab user={s.user} companyName={s.companyName} setCompanyName={s.setCompanyName} />
              )}
              {s.activeTab === "review" && <ReviewTab threshold={s.threshold} setThreshold={s.setThreshold} />}
              {s.activeTab === "notifications" && (
                <NotificationsTab
                  emailNotifs={s.emailNotifs}
                  setEmailNotifs={s.setEmailNotifs}
                  exportNotifs={s.exportNotifs}
                  setExportNotifs={s.setExportNotifs}
                />
              )}
              {s.activeTab === "appearance" && <AppearanceTab />}
              {s.activeTab === "security" && <SecurityTab />}
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}
