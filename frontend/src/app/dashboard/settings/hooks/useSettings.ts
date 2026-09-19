import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { getMe, getScannerConfig, updateProfile, updateScannerConfig, updateTenant } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { errorMessage } from "@/lib/errors";
import type { TabId, UserInfo } from "../types";

export function useSettings() {
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [user, setUser] = useState<UserInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [companyName, setCompanyName] = useState("");

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

  const canEditCompany = user?.role === "admin" || user?.role === "owner";
  // Appearance applies instantly (theme store) — nothing to save there.
  const canSave = activeTab !== "appearance";

  // Keep the top bar / user menu in sync with what was just saved.
  const applyUser = (me: UserInfo) => {
    setUser(me);
    setDisplayName(me.display_name);
    setCompanyName(me.tenant_name);
    const token = useAuthStore.getState().token ?? localStorage.getItem("token");
    if (token) useAuthStore.getState().setAuth(token, me);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (activeTab === "profile") {
        applyUser(await updateProfile({ display_name: displayName }));
      } else if (activeTab === "company") {
        applyUser(await updateTenant({ name: companyName }));
      } else if (activeTab === "review" && configLoaded) {
        await updateScannerConfig({ review_confidence_threshold: threshold });
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
    saving, saved, canSave, handleSave,
    displayName, setDisplayName,
    companyName, setCompanyName, canEditCompany,
    threshold, setThreshold,
  };
}
