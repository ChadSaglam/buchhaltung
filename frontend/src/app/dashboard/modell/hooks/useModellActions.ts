import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { downloadFilename } from "../helpers";
import type { DangerAction, DownloadType } from "../types";

export function useModellActions(fetchInfo: () => Promise<void>) {
  const [training, setTraining] = useState(false);
  const [dangerConfirm, setDangerConfirm] = useState<string | null>(null);

  const handleTrain = async () => {
    setTraining(true);
    try {
      const res = await api.post("/api/classify/train");
      toast.success(
        `Modell trainiert! ${res.data.total_samples} Samples, ${((res.data.cv_accuracy || 0) * 100).toFixed(1)}% Genauigkeit`
      );
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Training fehlgeschlagen");
    } finally {
      setTraining(false);
    }
  };

  const handleDangerAction = async (action: DangerAction) => {
    try {
      await api.delete(`/api/classify/${action}`);
      toast.success(
        action === "memory" ? "Gedächtnis gelöscht" :
        action === "corrections" ? "Korrekturen gelöscht" : "ML-Modell gelöscht"
      );
      setDangerConfirm(null);
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Aktion fehlgeschlagen");
    }
  };

  const handleDownload = async (type: DownloadType) => {
    try {
      const res = await api.get(`/api/classify/download/${type}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = downloadFilename(type);
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download fehlgeschlagen");
    }
  };

  // Upload model bundle
  const handleUploadBundle = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post("/api/classify/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Modell wiederhergestellt!");
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Upload fehlgeschlagen");
    }
  };

  return {
    training,
    handleTrain,
    dangerConfirm,
    setDangerConfirm,
    handleDangerAction,
    handleDownload,
    handleUploadBundle,
  };
}
