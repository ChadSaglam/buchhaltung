import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { ModelInfo, VisionStatus } from "../types";

export function useModellInfo() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [vision, setVision] = useState<VisionStatus>({ available: false, model_name: null, model_count: 0, is_cloud: false });
  const [loading, setLoading] = useState(true);

  const fetchInfo = useCallback(async () => {
    try {
      const [infoRes, visionRes] = await Promise.allSettled([
        api.get("/api/classify/info"),
        api.get("/api/scanner/vision-status")
      ]);
      if (infoRes.status === "fulfilled") setInfo(infoRes.value.data);
      if (visionRes.status === "fulfilled") setVision(visionRes.value.data);
    } catch {
      toast.error("Modell-Info konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchInfo(); }, [fetchInfo]);

  return { info, vision, loading, fetchInfo };
}
