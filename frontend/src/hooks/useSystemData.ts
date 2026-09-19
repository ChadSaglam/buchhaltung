"use client";
import { useApi } from "@/hooks/useApi";
import type { BookingStatsResponse, ClassifierInfoResponse, ReviewQueueResponse, ScannerStatusResponse } from "@/lib/api-schema";

/**
 * The handful of endpoints every dashboard surface reads (KPIs, system
 * checklist, getting-started, the bell). One SWR key each — however many
 * components mount, one request goes out, and one poll keeps them fresh (B-16).
 *
 * The response shapes come from the backend schema (B-59), not from hand-written
 * interfaces that drift.
 */
export const SYSTEM_POLL_MS = 60_000;

export type ClassifierInfo = ClassifierInfoResponse;
export type BookingStats = BookingStatsResponse;
export type ReviewQueue = ReviewQueueResponse;

/**
 * B-87: `/api/scanner/vision-status` is NOT untyped — it has had
 * `response_model=ScannerStatusResponse` since B-59, and this comment saying
 * otherwise is what kept two hand-written copies of it alive. This one happened
 * to name real fields; the copy in `modell/types.ts` named four that do not
 * exist, so the two pages disagreed about the same endpoint on the same screen.
 * One generated type, no copies.
 *
 * `/api/ai/status` really is still untyped — see AiStatus below.
 */
export type VisionStatus = ScannerStatusResponse;

export interface AiStatus {
  ok: boolean;
}

export const useClassifierInfo = () => useApi<ClassifierInfo>("/api/classify/info", { refreshInterval: SYSTEM_POLL_MS });
export const useBookingStats = () => useApi<BookingStats>("/api/bookings/stats", { refreshInterval: SYSTEM_POLL_MS });
export const useVisionStatus = () => useApi<VisionStatus>("/api/scanner/vision-status", { refreshInterval: SYSTEM_POLL_MS });
export const useAiStatus = () => useApi<AiStatus>("/api/ai/status", { refreshInterval: SYSTEM_POLL_MS });
export const useReviewQueue = () => useApi<ReviewQueue>("/api/review/", { refreshInterval: SYSTEM_POLL_MS });
