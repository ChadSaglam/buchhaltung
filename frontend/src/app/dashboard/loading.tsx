import { PageSkeleton } from "@/components/shared/PageSkeleton";

/** Shown instantly while a dashboard route streams in — no blank screen. */
export default function DashboardLoading() {
  return <PageSkeleton header metrics={4} rows={6} className="p-1" />;
}
