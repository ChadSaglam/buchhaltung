import { useEffect, useMemo, useState } from "react";
import { getBookings, type Booking } from "@/lib/api";
import {
  parseQuery, searchBookings, monthlyStats, detectAnomalies,
  type Anomaly, type MonthlyStats,
} from "@/lib/booking-analytics";
import { activeFilterLabels } from "../helpers";

export function useInsights() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await getBookings(undefined, 1000);
      setBookings((data as Booking[]) ?? []);
    } catch {
      setBookings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const parsed = useMemo(() => parseQuery(query), [query]);
  const results = useMemo(
    () => (query.trim() ? searchBookings(bookings, parsed) : bookings),
    [bookings, parsed, query]
  );
  const months: MonthlyStats[] = useMemo(() => monthlyStats(bookings), [bookings]);
  const anomalies: Anomaly[] = useMemo(() => detectAnomalies(bookings), [bookings]);
  const activeFilters = useMemo(() => activeFilterLabels(parsed), [parsed]);

  return { bookings, loading, load, query, setQuery, results, months, anomalies, activeFilters };
}
