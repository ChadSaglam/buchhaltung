"use client";
import { useApi } from "@/hooks/useApi";

/**
 * The handful of endpoints every dashboard surface reads (KPIs, system
 * checklist, getting-started, the bell). One SWR key each — however many
 * components mount, one request goes out, and one poll keeps them fresh (B-16).
 */
export const SYSTEM_POLL_MS = 60_000;

export interface ClassifierInfo {
  has_model: boolean;
  model_accuracy: number;
  train_accuracy: number;
  total_samples: number;
  classes: number;
  memory_count: number;
  correction_count: number;
}

export interface BookingStats {
  total_count: number;
  total_amount: number;
  by_source: Record<string, number>;
}

export interface VisionStatus {
  ok: boolean;
  best_vision?: string | null;
}

export interface AiStatus {
  ok: boolean;
}

export type ReviewQueue = unknown[] | { count?: number };

export const useClassifierInfo = () => useApi<ClassifierInfo>("/api/classify/info", { refreshInterval: SYSTEM_POLL_MS });
export const useBookingStats = () => useApi<BookingStats>("/api/bookings/stats", { refreshInterval: SYSTEM_POLL_MS });
export const useVisionStatus = () => useApi<VisionStatus>("/api/scanner/vision-status", { refreshInterval: SYSTEM_POLL_MS });
export const useAiStatus = () => useApi<AiStatus>("/api/ai/status", { refreshInterval: SYSTEM_POLL_MS });
export const useReviewQueue = () => useApi<ReviewQueue>("/api/review/", { refreshInterval: SYSTEM_POLL_MS });
