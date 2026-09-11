export interface Konto {
  konto: string;
  bezeichnung: string;
}

export interface ClassifyInfo {
  model_accuracy: number;
  memory_count: number;
  correction_count: number;
}

export type KontenplanTab = "kontenplan" | "training";
