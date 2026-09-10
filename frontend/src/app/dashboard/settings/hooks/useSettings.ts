import { useState, useEffect } from "react";
import { getMe, getScannerConfig, updateScannerConfig } from "@/lib/api";
import type { TabId, UserInfo } from "../types";

export function useSettings() {
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [user, setUser] = useState<UserInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [emailNotifs, setEmailNotifs] = useState(true);
  const [exportNotifs, setExportNotifs] = useState(true);

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

  return {
    activeTab, setActiveTab,
    user,
    saving, saved, handleSave,
    displayName, setDisplayName,
    companyName, setCompanyName,
    emailNotifs, setEmailNotifs,
    exportNotifs, setExportNotifs,
    threshold, setThreshold,
  };
}
