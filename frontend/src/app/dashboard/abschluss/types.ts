import type { Schemas } from "@/lib/api-schema";

export type PreflightResponse = Schemas["PreflightResponse"];
export type ExportCheck = Schemas["ExportCheck"];
export type ExportBatchOut = Schemas["ExportBatchOut"];
export type ExportBatchListResponse = Schemas["ExportBatchListResponse"];
export type MonthReportResponse = Schemas["MonthReportResponse"];
export type MonthListResponse = Schemas["MonthListResponse"];
export type MonthKpis = Schemas["MonthKpisOut"];
export type MwstReportResponse = Schemas["MwstReportResponse"];
export type QuarterListResponse = Schemas["QuarterListResponse"];
export type ZifferRow = Schemas["ZifferOut"];
export type MwstMethode = "effektiv" | "saldo";
