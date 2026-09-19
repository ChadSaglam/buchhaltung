import { useCallback, useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import toast from "react-hot-toast";
import { getReviewQueue, approveReviewItem, rejectReviewItem } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { moveSelection, reviewKeyFor, selectionAfterRemove } from "../helpers";
import type { ReviewQueue } from "../types";

type Decide = typeof approveReviewItem;

export function useReviewQueue() {
  const { data, error, isLoading, mutate } = useSWR<ReviewQueue>("/api/review/", getReviewQueue, {
    revalidateOnFocus: false,
  });
  const [selected, setSelected] = useState(-1);
  const items = useMemo(() => data?.items ?? [], [data]);
  const threshold = typeof data?.threshold === "number" ? data.threshold : 0.8;

  // Optimistic (B-14): the row leaves immediately; if the server says no, it comes back.
  const decide = useCallback(
    async (id: number, action: Decide) => {
      const before = data;
      const idx = items.findIndex((i) => i.id === id);
      if (!before || idx < 0) return;
      setSelected((s) => selectionAfterRemove(s, idx, items.length));
      await mutate({ ...before, items: before.items.filter((i) => i.id !== id) }, { revalidate: false });
      try {
        await action(id);
      } catch (e) {
        await mutate(before, { revalidate: false });
        setSelected(idx);
        toast.error(errorMessage(e));
      }
    },
    [data, items, mutate],
  );
  const approve = useCallback((id: number) => decide(id, approveReviewItem), [decide]);
  const reject = useCallback((id: number) => decide(id, rejectReviewItem), [decide]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      const key = reviewKeyFor(e);
      if (!key || items.length === 0) return;
      e.preventDefault();
      if (key === "next" || key === "prev") {
        setSelected((s) => moveSelection(s, key, items.length));
        return;
      }
      const item = items[selected];
      if (!item) return;
      void (key === "approve" ? approve(item.id) : reject(item.id));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, selected, approve, reject]);

  return { items, threshold, error, isLoading, retry: () => mutate(), selected, setSelected, approve, reject };
}
