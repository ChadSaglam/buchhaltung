import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { getMe, getScannerConfig, updateScannerConfig } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
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
  const [loading, setLoading] = useState(true);
  // The profile is the one request the page cannot do without; the scanner
  // config only feeds the review tab and degrades to its default.
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [me, cfg] = await Promise.allSettled([getMe(), getScannerConfig()]);
    if (me.status === "fulfilled") {
      setUser(me.value);
      setDisplayName(me.value.display_name);
      setCompanyName(me.value.tenant_name);
    } else {
      setError(me.reason);
    }
    if (cfg.status === "fulfilled" && typeof cfg.value.review_confidence_threshold === "number") {
      setThreshold(cfg.value.review_confidence_threshold);
    }
    setConfigLoaded(true);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

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
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return {
    activeTab, setActiveTab,
    user, loading, error, load,
    saving, saved, handleSave,
    displayName, setDisplayName,
    companyName, setCompanyName,
    emailNotifs, setEmailNotifs,
    exportNotifs, setExportNotifs,
    threshold, setThreshold,
  };
}
