import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { ModelInfo, VisionStatus } from "../types";

export function useModellInfo() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [vision, setVision] = useState<VisionStatus>({ available: false, model_name: null, model_count: 0, is_cloud: false });
  const [loading, setLoading] = useState(true);
  // Only the classifier info is essential: without it the page has nothing to
  // show. A missing vision status just reads as "Vision fehlt".
  const [error, setError] = useState<unknown>(null);

  const fetchInfo = useCallback(async () => {
    setError(null);
    const [infoRes, visionRes] = await Promise.allSettled([
      api.get("/api/classify/info"),
      api.get("/api/scanner/vision-status"),
    ]);
    if (infoRes.status === "fulfilled") setInfo(infoRes.value.data);
    else setError(infoRes.reason);
    if (visionRes.status === "fulfilled") setVision(visionRes.value.data);
    setLoading(false);
  }, []);

  useEffect(() => { fetchInfo(); }, [fetchInfo]);

  return { info, vision, loading, error, fetchInfo };
}
