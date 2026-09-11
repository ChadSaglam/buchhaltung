"use client";

import { useDropzone } from "react-dropzone";
import { Upload, Download, Package } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import type { DownloadType, ModelInfo } from "../types";

interface ExportCardProps {
  info: ModelInfo | null;
  handleDownload: (type: DownloadType) => void;
}

export function ExportCard({ info, handleDownload }: ExportCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Download className="w-4 h-4 text-info" />
          <CardTitle>Modell exportieren</CardTitle>
        </div>
        <CardDescription>Sicherung inkl. ML-Modell, Gedächtnis, Kontenplan & Korrekturen</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleDownload("bundle")}
            disabled={!info?.has_model && (info?.memory_count ?? 0) === 0}
            icon={<Package className="w-4 h-4" />}
          >
            Komplettpaket .zip
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDownload("model")}
            disabled={!info?.has_model}
          >
            Nur ML .pkl
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDownload("memory")}
            disabled={(info?.memory_count ?? 0) === 0}
          >
            Nur Gedächtnis .json
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function RestoreCard({ handleUploadBundle }: { handleUploadBundle: (file: File) => void }) {
  const {
    getRootProps: getRestoreProps,
    getInputProps: getRestoreInputProps,
  } = useDropzone({
    onDrop: (files) => files[0] && handleUploadBundle(files[0]),
    accept: {
      "application/zip": [".zip"],
      "application/octet-stream": [".pkl"],
      "application/json": [".json"],
    },
    maxFiles: 1,
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Upload className="w-4 h-4 text-success" />
          <CardTitle>Modell importieren</CardTitle>
        </div>
        <CardDescription>Ein zuvor gesichertes Modell-Paket wiederherstellen</CardDescription>
      </CardHeader>
      <CardContent>
        <div
          {...getRestoreProps()}
          className="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-500/6 transition-all"
        >
          <input {...getRestoreInputProps({ "aria-label": "Modell-Bundle auswählen" })} />
          <Upload className="w-6 h-6 text-muted-foreground/40 mx-auto mb-1" />
          <p className="text-xs text-muted-foreground">.zip / .pkl / .json hierher ziehen</p>
        </div>
      </CardContent>
    </Card>
  );
}
