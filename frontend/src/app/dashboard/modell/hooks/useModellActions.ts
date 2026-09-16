import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { downloadFilename } from "../helpers";
import type { DangerAction, DownloadType } from "../types";

export function useModellActions(fetchInfo: () => Promise<void>) {
  const [training, setTraining] = useState(false);
  const [dangerConfirm, setDangerConfirm] = useState<string | null>(null);
  // B-58: a destructive call and a restore both take seconds. Without a busy
  // flag the button stayed live and a second click fired the same request.
  const [dangerBusy, setDangerBusy] = useState<DangerAction | null>(null);
  const [restoring, setRestoring] = useState(false);

  const handleTrain = async () => {
    setTraining(true);
    try {
      const res = await api.post("/api/classify/train");
      toast.success(
        `Modell trainiert! ${res.data.total_samples} Samples, ${((res.data.cv_accuracy || 0) * 100).toFixed(1)}% Genauigkeit`
      );
      fetchInfo();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setTraining(false);
    }
  };

  const handleDangerAction = async (action: DangerAction) => {
    if (dangerBusy) return;
    setDangerBusy(action);
    try {
      await api.delete(`/api/classify/${action}`);
      toast.success(
        action === "memory" ? "Gedächtnis gelöscht" :
        action === "corrections" ? "Korrekturen gelöscht" : "ML-Modell gelöscht"
      );
      setDangerConfirm(null);
      fetchInfo();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDangerBusy(null);
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
    if (restoring) return;
    // Restoring replaces the model, the memory and the Kontenplan — ask first.
    const ok = window.confirm(
      `„${file.name}" wiederherstellen?\n\nDas ersetzt das aktuelle ML-Modell, das Gedächtnis und den Kontenplan. Exportieren Sie vorher ein Komplettpaket, wenn Sie zurück wollen.`,
    );
    if (!ok) return;
    setRestoring(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post("/api/classify/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Modell wiederhergestellt!");
      fetchInfo();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRestoring(false);
    }
  };

  return {
    training,
    handleTrain,
    dangerConfirm,
    setDangerConfirm,
    dangerBusy,
    handleDangerAction,
    handleDownload,
    handleUploadBundle,
    restoring,
  };
}
