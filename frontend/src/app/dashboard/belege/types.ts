import type { Schemas } from "@/lib/api-schema";

export type DocumentOut = Schemas["DocumentOut"];
export type DocumentStatus = "offen" | "bezahlt" | "exportiert" | "fehler";
export type DocumentSummary = Schemas["DocumentSummary"];
export type UploadResponse = Schemas["DocumentUploadResponse"];
