import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { IMPORT_EXTENSIONS, fileExtension } from "../helpers";
import type { ImportResult } from "../types";

export function useBananaImport(fetchInfo: () => Promise<void>) {
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [replaceData, setReplaceData] = useState(false);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    if (!IMPORT_EXTENSIONS.includes(fileExtension(file.name))) {
      toast.error("Nur XLS, XLSX oder CSV Dateien erlaubt");
      return;
    }
    setImporting(true);
    setImportResult(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post(
        `/api/import/banana?replace=${replaceData}&also_memory=true&auto_train=true`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setImportResult(res.data);
      toast.success(`${res.data.imported} Buchungen importiert & Modell trainiert!`);
      fetchInfo();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Import fehlgeschlagen");
    } finally {
      setImporting(false);
    }
  }, [replaceData, fetchInfo]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.ms-excel": [".xls"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "text/csv": [".csv"],
    },
    maxFiles: 1,
    disabled: importing,
  });

  return {
    importing,
    importResult,
    replaceData,
    setReplaceData,
    getRootProps,
    getInputProps,
    isDragActive,
  };
}
