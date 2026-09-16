/**
 * B-59: both shapes are generated from the backend schema. The aliases stay so
 * the components keep their short local names.
 */
import type { ReviewItemOut, ReviewQueueResponse } from "@/lib/api-schema";

export type ReviewItem = ReviewItemOut;
export type ReviewQueue = ReviewQueueResponse;
