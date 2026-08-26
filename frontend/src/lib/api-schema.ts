/**
 * Hand-written, stable aliases over the auto-generated OpenAPI types.
 *
 * Import from here (not from `api-types` directly) so a backend rename shows up
 * as one compile error in this file instead of scattered across the app.
 */
import type { components, paths } from "./api-types";

export type Schemas = components["schemas"];
export type Paths = paths;

/** Response body of a successful `GET`/`POST` on `P`. */
export type ApiResponse<
  P extends keyof paths,
  M extends keyof paths[P],
> = paths[P][M] extends { responses: { 200: { content: { "application/json": infer R } } } } ? R : never;

/** JSON request body for `M` on `P`. */
export type ApiBody<
  P extends keyof paths,
  M extends keyof paths[P],
> = paths[P][M] extends { requestBody: { content: { "application/json": infer B } } } ? B : never;

// --- Domain aliases used across the app -------------------------------------
export type TokenResponse = Schemas["TokenResponse"];
export type UserResponse = Schemas["UserResponse"];
export type LoginRequest = Schemas["LoginRequest"];
export type RegisterRequest = Schemas["RegisterRequest"];
export type BookingCreate = Schemas["BookingCreate"];
export type ClassifyRequest = Schemas["ClassifyRequest"];
export type PredictRequest = Schemas["PredictRequest"];
export type CorrectRequest = Schemas["CorrectRequest"];
export type ExtractedInvoice = Schemas["ExtractedInvoice"];
export type ExtractedLineItem = Schemas["ExtractedLineItem"];
export type ScannerExtractResponse = Schemas["ScannerExtractResponse"];
export type ScannerStatusResponse = Schemas["ScannerStatusResponse"];
export type ScannerConfigResponse = Schemas["app__schemas__scanner__ScannerConfigResponse"];
export type ScannerConfigUpdate = Schemas["app__schemas__scanner__ScannerConfigUpdate"];
export type ChatRequest = Schemas["ChatRequest"];
export type ChatMessage = Schemas["ChatMessage"];
export type ExportRequest = Schemas["ExportRequest"];
export type EmailRequest = Schemas["EmailRequest"];
export type ApproveRequest = Schemas["ApproveRequest"];
export type KontenplanUpdate = Schemas["KontenplanUpdate"];
