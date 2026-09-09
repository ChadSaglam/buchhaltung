export interface ModelInfo {
  has_model: boolean;
  model_accuracy: number;
  train_accuracy: number;
  total_samples: number;
  classes: number;
  memory_count: number;
  correction_count: number;
  trained_at: string;
  sklearn_version: string;
  model_size_kb: number;
  memory_size_kb: number;
}

export interface VisionStatus {
  available: boolean;
  model_name: string | null;
  model_count: number;
  is_cloud: boolean;
}

export interface ClassifyResult {
  source: string;
  kt_soll: string;
  kt_soll_name: string;
  kt_haben: string;
  kt_haben_name: string;
  mwst_code: string;
  mwst_pct: number;
  confidence: number;
  top_predictions?: { klass: string; name: string; probability: number }[];
}

export interface MemoryEntry {
  lookup_key: string;
  beschreibung: string;
  kt_soll: string;
  kt_haben: string;
  mwst_code: string;
  mwst_pct: number;
}

export interface ImportResult {
  imported: number;
  memory_entries: number;
  training?: {
    total_samples: number;
    classes: number;
    cv_accuracy: number | null;
    train_accuracy: number;
  };
}

export interface TrainingData {
  konto_soll: string;
  bezeichnung: string;
  anzahl: number;
}

export type InspectTab = "test" | "top" | "memory" | "retrain";
export type DangerAction = "memory" | "corrections" | "model";
export type DownloadType = "bundle" | "model" | "memory";
